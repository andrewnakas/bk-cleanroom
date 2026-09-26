"""DIRTY ROOM: derive the v1.0 -> v1.1 asset ID map from code.

The decomp builds v1.0 code, whose asset IDs follow the v1.0 table; v1.1 renumbered the
dialog/quiz range (packed) and shifted everything after it. We align our v1.0 build with the
retail v1.1 code, function by function (relocations masked) and data section by data section,
and collect every constant that differs where both sides look like asset IDs.

    python -m games.bk.idmap <build.elf> <uncompressed.z64> <v1.1 rom> <out.json>
Output: {"pairs": [[v10, v11, count], ...]} plus a one-screen summary.
"""
import collections
import difflib
import json
import struct
import sys

from games.bk.assetfs import unzip
from games.bk.funcdiff import mask, words
from games.bk.romtool import symbols

# overlay order of the compressed code in the ROM (bk_rom_compress swaps entries 3 and 4)
ROM_ORDER = ["core1", "core2", "CC", "MMM", "GV", "TTC", "MM", "BGS", "RBB", "FP", "SM", "cutscenes",
             "lair", "fight", "CCW", "emptyLvl"]
LO, HI = 0x2D0, 0x1700      # v1.0 IDs that can differ (models/sprites on; anims are below)


# rzip stream offsets in the US v1.1 ROM (text, data per overlay, ROM_ORDER), found by scanning
V11_STREAMS = [0xF1C830, 0xF391BB, 0xF3ADB0, 0xF9FA9E, 0xFA6F80, 0xFA8D34, 0xFA8EE0, 0xFABC75, 0xFAC0E0,
               0xFB1228, 0xFB1810, 0xFB4A9C, 0xFB5450, 0xFB727E, 0xFB7480, 0xFBC5A9, 0xFBC9C0, 0xFC1598,
               0xFC1BA0, 0xFC6FB2, 0xFC77E0, 0xFC9BDF, 0xFC9EF0, 0xFCBACD, 0xFCC120, 0xFD2677, 0xFD3400,
               0xFD8ABF, 0xFD91F0, 0xFDD36B, 0xFDDA80, 0xFDDA8E]


def v11_overlays(rom):
    out = [unzip(rom[o:o + 0x100000]) for o in V11_STREAMS]
    return {n: out[2 * k:2 * k + 2] for k, n in enumerate(ROM_ORDER)}


def text_pairs(ours_text, v11_text, funcs):
    rt = words(v11_text)
    index = collections.defaultdict(list)
    for i in range(len(rt) - 4):
        index[tuple(rt[i:i + 4])].append(i)
    pairs = collections.Counter()
    matched = 0
    for a, b in funcs:
        seg = ours_text[a:b]
        k = words(seg)
        if len(k) < 4:
            continue
        for i in index.get(tuple(k[:4]), []):
            if rt[i:i + len(k)] == k:
                matched += 1
                ow = struct.unpack(">%dI" % len(k), seg[:4 * len(k)])
                vw = struct.unpack(">%dI" % len(k), v11_text[4 * i:4 * i + 4 * len(k)])
                for x, y in zip(ow, vw):
                    if x != y and (x >> 26) in (0x09, 0x0D, 0x0A, 0x0B) and ((x >> 21) & 31) == 0:
                        ix, iy = x & 0xFFFF, y & 0xFFFF
                        if LO <= ix < HI and LO <= iy < HI:
                            pairs[(ix, iy)] += 1
                break
    return pairs, matched


def data_pairs(ours, v11):
    a = struct.unpack(">%dH" % (len(ours) // 2), ours[:len(ours) // 2 * 2])
    b = struct.unpack(">%dH" % (len(v11) // 2), v11[:len(v11) // 2 * 2])
    # align on halfwords outside the ID range (IDs are what differs)
    ka = [x if not (LO <= x < HI) else -1 for x in a]
    kb = [x if not (LO <= x < HI) else -1 for x in b]
    pairs = collections.Counter()
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace") and i2 - i1 == j2 - j1:
            for x, y in zip(a[i1:i2], b[j1:j2]):
                if x != y and LO <= x < HI and LO <= y < HI:
                    pairs[(x, y)] += 1
    return pairs


def main(argv):
    elf, unc, v11p, out = argv[1:5]
    s = symbols(elf)
    rom = open(unc, "rb").read()
    ret = open(v11p, "rb").read()
    v11 = v11_overlays(ret)
    total = collections.Counter()
    for name in ROM_ORDER:
        ts = s[f"{name}_TEXT_START"]
        te = s[f"{name}_DATA_START_OFFSET" if name == "core1" else f"{name}_TEXT_END"]
        r0 = s[f"{name}_ROM_START"]
        r1 = s[f"{name}_ROM_END"]
        text = rom[r0:r0 + (te - ts)]
        data = rom[r0 + (te - ts):r1]
        fn = sorted(a for n, a in s.items() if ts <= a < te and not n.startswith(("D_", ".", "L", "jtbl")) and "_ROM_" not in n)
        spans = [(fn[i] - ts, (fn[i + 1] if i + 1 < len(fn) else te) - ts) for i in range(len(fn))]
        tp, m = text_pairs(text, v11[name][0], spans)
        dp = data_pairs(data, v11[name][1])
        total.update(tp)
        total.update(dp)
        print(f"{name:10s} funcs {m}/{len(spans)} matched; text pairs {len(tp)}, data pairs {len(dp)}")
    # consistency: one v11 per v10
    by10 = collections.defaultdict(collections.Counter)
    for (x, y), c in total.items():
        by10[x][y] += c
    conflicts = {hex(x): {hex(y): c for y, c in v.items()} for x, v in by10.items() if len(v) > 1}
    best = sorted((x, v.most_common(1)[0][0], sum(v.values())) for x, v in by10.items())
    json.dump({"pairs": best, "conflicts": conflicts}, open(out, "w"), indent=0)
    offs = collections.Counter(x - y for x, y, _ in best)
    print(f"{len(best)} v1.0 IDs mapped; {len(conflicts)} with conflicting candidates; offsets: "
          + ", ".join(f"{o:#x}x{c}" for o, c in sorted(offs.items())))


if __name__ == "__main__":
    main(sys.argv)
