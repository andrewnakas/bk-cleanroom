"""DIRTY ROOM dev check: find functions of our build whose code differs from retail v1.1.

    python -m games.bk.funcdiff <build.elf> <uncompressed.z64> <v1.1 rom> [overlay=core1] [--all]
Each function's words are compared with relocatable immediates masked (lui/addiu/ori/lw/sw/
jal/j ...); a function is "ok" when its masked word sequence occurs in the retail overlay.
Only a code sanity check (libultra and unchanged game code should match).
"""
import struct
import sys

from games.bk.dirty_rom import unz
from games.bk.romtool import symbols

V11_OVL = {"core1": (0xF1C830, 0x36EF0), "core2": (0xF3ADB0, 0xDC9C0)}


def mask(w):
    op = w >> 26
    if op in (2, 3):                   # j/jal
        return w & 0xFC000000
    if op in (0x0F, 0x09, 0x0D, 0x23, 0x2B, 0x21, 0x25, 0x20, 0x24, 0x29, 0x28, 0x31, 0x39, 0x35, 0x3D, 0x37,
              0x3F, 0x19, 0x0C, 0x0A, 0x0B, 0x08, 0x22, 0x26, 0x2A, 0x2E):
        return w & 0xFFFF0000          # I-type with symbol/const immediates
    return w


def words(b):
    return [mask(w) for w in struct.unpack(">%dI" % (len(b) // 4), b[:len(b) // 4 * 4])]


def main(argv):
    elf, unc, v11 = argv[1], argv[2], argv[3]
    ovl = argv[4] if len(argv) > 4 and not argv[4].startswith("-") else "core1"
    s = symbols(elf)
    rom = open(unc, "rb").read()
    retail = open(v11, "rb").read()
    off, size = V11_OVL[ovl]
    rt = words(unz(retail, off, size))
    rts = ",".join(map(str, rt))
    vram = s[f"{ovl}_TEXT_START"]
    rom0 = s[f"{ovl}_ROM_START"]
    tend = s[f"{ovl}_DATA_START_OFFSET" if ovl == "core1" else f"{ovl}_TEXT_END"]
    fn = sorted((a, n) for n, a in s.items() if vram <= a < tend and not n.startswith(("D_", ".", "L")) and "_ROM_" not in n)
    bad, ok = [], 0
    for i, (a, n) in enumerate(fn):
        e = fn[i + 1][0] if i + 1 < len(fn) else tend
        if e - a < 16:
            continue
        b = rom[rom0 + (a - vram):rom0 + (e - vram)]
        key = ",".join(map(str, words(b)))
        if key in rts:
            ok += 1
        else:
            bad.append((n, e - a))
    lib = [b for b in bad if b[0].startswith(("os", "__os", "_os", "__", "al", "n_al", "gu", "sp"))]
    print(f"{ovl}: {ok} functions match retail v1.1, {len(bad)} differ ({len(lib)} libultra-like)")
    for n, sz in (bad if "--all" in argv else lib)[:40]:
        print(f"  {n} ({sz:#x})")


if __name__ == "__main__":
    main(sys.argv)
