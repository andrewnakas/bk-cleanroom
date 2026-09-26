"""DIRTY ROOM: build a v1.0-layout 'decompressed' image from a US Rev 1 (v1.1) ROM.

The decomp only builds US v1.0 (splat yaml + symbols). We own a v1.1 cart, whose
code differs, so we cannot make the real decompressed.us.v10.z64. The v1.0 code is
100% C in the decomp, so splat only needs bytes for the non-C segments:
  header/ipl3/boot (0..0x5E90), soundfont ctl/tbl, 3 tiny hand-written asm files
  in core1, and the RSP microcode text/data at the end of core1.
Everything else is left zero. Assets come from the v1.1 asset filesystem
(bin/assets.bin) and are later replaced by clean regenerated ones.

    python -m games.bk.dirty_rom <v1.1 rom.z64> <dirty tree>
"""
import struct
import sys
import zlib
from pathlib import Path

V11_DELTA = 0x35E0            # v1.1 ROM offset - v1.0 ROM offset, assets .. core1
CORE1_V11 = (0xF1C830, 0x36EF0, 0xF391BB, 0x4A00)   # text rzip, size, data rzip, size
V10_SIZE = 0x10BCD20
ASSETS = 0x5E90
SOUND_V10 = (0xD846C0, 0xF19250)
# (v1.0 decompressed ROM offset, v1.1 core1 text offset, size)
HASM = [(0xF2E840, 0x146E0, 0x40),     # bkmemops64
        (0xF36810, 0x1C6B0, 0x10),     # bkgetsr
        (0xF37A70, 0x1D910, 0xA0)]     # code_1E820
UCODE_TEXT_V10 = (0xF4DDC0, 0xF50E40)  # end of core1 .text
UCODE_DATA_V10 = (0xF546B0, 0xF55960)  # end of core1 .data


def unz(rom, off, size):
    assert rom[off:off + 2] == b"\x11\x72"
    return zlib.decompressobj(-15).decompress(rom[off + 6:off + 6 + 0x100000], size)


def assets_bin(rom):
    n = struct.unpack(">I", rom[ASSETS:ASSETS + 4])[0]
    last = struct.unpack(">I", rom[ASSETS + 8 + 8 * (n - 1):ASSETS + 12 + 8 * (n - 1)])[0]
    return rom[ASSETS:ASSETS + 8 + 8 * n + last]


def build(rom):
    out = bytearray(V10_SIZE)
    out[0:ASSETS] = rom[0:ASSETS]
    a, b = SOUND_V10
    out[a:b] = rom[a + V11_DELTA:b + V11_DELTA]
    text = unz(rom, CORE1_V11[0], CORE1_V11[1])
    data = unz(rom, CORE1_V11[2], CORE1_V11[3])
    for v10, v11, n in HASM:
        out[v10:v10 + n] = text[v11:v11 + n]
    a, b = UCODE_TEXT_V10
    out[a:b] = text[-(b - a):]
    a, b = UCODE_DATA_V10
    out[a:b] = data[-(b - a):]
    return out


def main(argv):
    rom = Path(argv[1]).read_bytes()
    tree = Path(argv[2])
    img = build(rom)
    (tree / "decompressed.us.v10.z64").write_bytes(img)
    ab = assets_bin(rom)
    (tree / "assets.v11.bin").write_bytes(ab)
    print(f"decompressed.us.v10.z64 {len(img):#x}; assets.v11.bin {len(ab):#x}")


if __name__ == "__main__":
    main(sys.argv)
