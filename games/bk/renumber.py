"""Renumber the v1.1 asset table into v1.0 asset IDs (what the decomp's v1.0 code asks for).

    python -m games.bk.renumber <idmap.json from games.bk.idmap> <out map json> <decomp tree>   (dirty room, once)
    renumber.apply(entries, mapping) -> entries in v1.0 slots (library use)

Map: v1.1 IDs < 0x8A3 are the same. The dialog/quiz range (v1.1 0x8A3..0xCC7, packed) is spread
over v1.0 0x8A3..0x146A. Offsets (v1.0 - v1.1) come from code alignment (idmap.py, anchor groups of
>= 9 pairs), two text anchors (Brentilda, final boss) and the quiz ranges in code_91E10.c. An
unanchored ID continues the previous anchor's offset while it stays below the next anchor's v1.0
start, so "id + k" arithmetic in code keeps working. From v1.1 0xCC8 (level models, midi) on: +0x7A3.
"""
import collections
import json
import sys

SEG5_V11, SEG5_OFF = 0xCC8, 0x7A3
EXTRA = {0xB67: 0x53A, 0xB69: 0x57E,          # Brentilda meet/heal, final boss entering (idmap, text-checked)
         0xC00: 0x613, 0xC64: 0x677, 0xC77: 0x72C, 0xCAA: 0x75D}   # quiz 0x1213, picture 0x12DB, sound 0x13A3, grunty 0x1407


def ver_select_pairs(tree):
    """(v1.0, PAL) asset pairs from the decomp's VER_SELECT calls (PAL == v1.1 in the dialog range)."""
    import glob
    import re
    enum = {}
    for l in open(f"{tree}/include/enums.h", encoding="latin1"):
        m = re.match(r"\s*(ASSET_([0-9A-F]+)_\w+)", l)
        if m:
            enum[m.group(1)] = int(m.group(2), 16)
    out = set()
    for f in glob.glob(f"{tree}/src/**/*.c", recursive=True):
        for m in re.finditer(r"VER_SELECT\(\s*(ASSET_\w+|0x[0-9A-Fa-f]+)\s*,\s*(0x[0-9A-Fa-f]+)\s*,", open(f, encoding="latin1").read()):
            a = enum.get(m.group(1), int(m.group(1), 16) if m.group(1).startswith("0x") else None)
            b = int(m.group(2), 16)
            if a and 0x8A3 <= a < 0x146B and 0x8A3 <= b < SEG5_V11:
                out.add((a, b))
    return sorted(out)


def build_map(pairs, vs=()):
    offc = collections.Counter(x - y for x, y, c in pairs)
    anchors = {y: x - y for x, y in vs}
    for x, y, c in pairs:
        o = x - y
        if offc[o] >= 9 and 0x8A3 <= y < SEG5_V11:
            anchors[y] = o
    anchors.update(EXTRA)
    # keep a monotonic chain (drop anchors that would reorder)
    pts = sorted(anchors.items())
    chain = []
    for y, o in pts:
        if chain and y + o <= chain[-1][0] + chain[-1][1]:
            continue
        if not chain or o != chain[-1][1] or True:
            chain.append((y, o))
    # segment starts: first v11 id of each offset run
    starts = []
    for y, o in chain:
        if not starts or starts[-1][1] != o:
            starts.append((y, o))
    m = {}
    for i in range(0x8A3):
        m[i] = i
    k = -1
    for y in range(0x8A3, SEG5_V11):
        while k + 1 < len(starts) and starts[k + 1][0] <= y:
            k += 1
        if k < 0:
            o = starts[0][1]                      # before the first anchor: same offset as block 0
        else:
            o = starts[k][1]
            nxt = starts[k + 1] if k + 1 < len(starts) else (SEG5_V11, SEG5_OFF)
            if y + o >= nxt[0] + nxt[1]:          # would run into the next anchored run
                o = nxt[1]
        m[y] = y + o
    for y in range(SEG5_V11, 0x1000):
        m[y] = y + SEG5_OFF
    return m, starts


def apply(entries, mapping):
    """entries: assetfs.parse() of the v1.1 table. Returns a list in v1.0 slot order."""
    from games.bk.assetfs import Entry
    n10 = max(mapping[e.uid] for e in entries if e.data is not None) + 2
    out = [Entry(i, 0, False, 4, None) for i in range(n10)]
    for e in entries:
        if e.data is None:
            continue
        j = mapping[e.uid]
        assert out[j].data is None, f"slot {j:#x} taken twice"
        out[j] = Entry(j, e.seg, e.compressed, e.flags, e.data, e.raw)
    return out


def main(argv):
    pairs = json.load(open(argv[1]))["pairs"]
    vs = ver_select_pairs(argv[3]) if len(argv) > 3 else []
    m, starts = build_map(pairs, vs)
    vals = [m[k] for k in sorted(m)]
    assert len(set(vals)) == len(vals), "map not injective"
    json.dump({"v11_to_v10": {f"{k:#x}": f"{v:#x}" for k, v in sorted(m.items()) if k != v}}, open(argv[2], "w"), indent=0)
    # check against every pair seen
    ok = sum(1 for x, y, c in pairs if m.get(y) == x)
    okv = sum(1 for x, y in vs if m.get(y) == x)
    print(f"VER_SELECT pairs agreeing: {okv}/{len(vs)}")
    print(f"renumber: {len(starts)} offset runs {[(hex(y), hex(o)) for y, o in starts]}; "
          f"agrees with {ok}/{len(pairs)} code pairs; v1.0 slots up to {max(vals):#x}")


if __name__ == "__main__":
    main(sys.argv)
