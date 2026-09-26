"""Python port of the decomp's bk_rom_compress (its rarezip C library does not build on Windows).

    python -m games.bk.romtool --symbols <elf> <uncompressed.z64> <out.txt>
    python -m games.bk.romtool <elf> <uncompressed.z64> <out.z64>
Overlays are raw-deflated with the BK header (0x11 0x72, u32 size); the per-overlay anti-tamper
CRC words are patched as the original tool does, then the CIC header checksum.
Symbols come from `mips64-elf-nm`.
"""
import os
import subprocess
import sys

from games.bk.assetfs import zip_

NM = os.path.expanduser("~/.local/mips64/bin/mips64-elf-nm.exe")
OVERLAYS = ["core1", "core2", "CC", "GV", "MMM", "TTC", "MM", "BGS", "RBB", "FP", "SM", "cutscenes",
            "lair", "fight", "CCW", "emptyLvl"]
# (overlay, code crc0 sym, code crc1 sym, data crc sym)
LEVEL_CRCS = [("SM", "D_8038AAE0", "D_8038AAE4", "D_8038AAE8"),
              ("MM", "D_803899C0", "D_803899C4", "D_803899C8"),
              ("TTC", "D_8038C750", "D_8038C754", "D_8038C758"),
              ("BGS", "D_80390B20", "D_80390B24", "D_80390B28"),
              ("CC", "D_80389BE0", "D_80389BE4", "D_80389BE8"),
              ("GV", "D_80390F30", "D_80390F34", "D_80390F38"),
              ("MMM", "D_8038C300", "D_8038C304", "D_8038C308")]
M32 = 0xFFFFFFFF


def symbols(elf):
    out = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout
    s = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3:
            s.setdefault(p[2], int(p[0], 16))
    return s


def bk_crc(b):
    a, x = 0, M32
    for byte in b:
        a = (a + byte) & M32
        x ^= (byte << (a & 0x17)) & M32
    return a, x


def bk_crc_fast(b):
    # same as bk_crc, vectorised: a_i = prefix sums, x = xor of byte << (a_i & 0x17)
    import numpy as np
    v = np.frombuffer(bytes(b), dtype=np.uint8).astype(np.uint64)
    a = np.cumsum(v) & M32
    sh = (v << (a & 0x17)) & M32
    x = np.bitwise_xor.reduce(sh.astype(np.uint32)) if len(sh) else 0
    return int(a[-1]) if len(a) else 0, int(x) ^ M32


class Ovl:
    def __init__(self, s, name):
        g = lambda k: s[k]
        self.name = name
        ts = g(f"{name}_TEXT_START")
        te = g(f"{name}_DATA_START_OFFSET" if name == "core1" else f"{name}_TEXT_END")
        self.text_len = te - ts
        self.data_start = g(f"{name}_DATA_START_OFFSET" if name == "core1" else f"{name}_DATA_START")
        self.rom = (g(f"{name}_ROM_START"), g(f"{name}_ROM_END"))


def put(buf, base, s, sym, val):
    if sym not in s:
        print(f"warning: could not find {sym}")
        return
    o = s[sym] - base
    buf[o:o + 4] = (val & M32).to_bytes(4, "big")


def cic_crc(rom):
    """CIC checksum (BK carts use the 6103 boot code)."""
    import zlib
    kind = {0x6170A4A1: 6101, 0x90BB6CB5: 6102, 0x0B050EE0: 6103}[zlib.crc32(bytes(rom[0x40:0x1000]))]
    t1 = t2 = t3 = t4 = t5 = t6 = 0xA3886759 if kind == 6103 else 0xF8CA4DDC
    import struct
    words = struct.unpack(">%dI" % (0x100000 // 4), bytes(rom[0x1000:0x101000]))
    for d in words:
        if (t6 + d) & M32 < t6:
            t4 = (t4 + 1) & M32
        t6 = (t6 + d) & M32
        t3 ^= d
        sh = d & 0x1F
        r = ((d << sh) | (d >> (32 - sh))) & M32 if sh else d
        t5 = (t5 + r) & M32
        t2 ^= r if t2 > d else (t6 ^ d)
        t1 = (t1 + (d ^ t5)) & M32
    if kind == 6103:
        return ((t6 ^ t4) + t3) & M32, ((t5 ^ t2) + t1) & M32
    return t6 ^ t4 ^ t3, t5 ^ t2 ^ t1


def main(argv):
    sym_mode = argv[1] in ("-s", "--symbols")
    if sym_mode:
        argv = argv[1:]
    elf, unc, out = argv[1], argv[2], argv[3]
    rom = open(unc, "rb").read()
    s = symbols(elf)
    crc = bk_crc_fast
    boot = Ovl(s, "boot_bk_boot")
    boot_bytes = rom[boot.rom[0]:boot.rom[1]]
    ovs = [Ovl(s, n) for n in OVERLAYS]
    code = [rom[o.rom[0]:o.rom[0] + o.text_len] for o in ovs]
    data = [bytearray(rom[o.rom[0] + o.text_len:o.rom[1]]) for o in ovs]
    code_crc = [crc(c) for c in code]
    idx = {n: i for i, n in enumerate(OVERLAYS)}
    sm_complete = None
    for name, c0, c1, dc in LEVEL_CRCS:
        i = idx[name]
        put(data[i], ovs[i].data_start, s, c0, code_crc[i][0])
        put(data[i], ovs[i].data_start, s, c1, code_crc[i][1])
        put(data[i], ovs[i].data_start, s, dc, 0)
        put(data[i], ovs[i].data_start, s, dc, crc(data[i])[0])
        if name == "SM":
            sm_complete = crc(data[i])
    i = idx["core2"]
    put(data[i], ovs[i].data_start, s, "D_803727F4", code_crc[i][1])
    core2_data_crc = crc(data[i])
    i = idx["core1"]
    put(data[i], ovs[i].data_start, s, "D_80276574", core2_data_crc[1])
    put(data[i], ovs[i].data_start, s, "D_80275650", sm_complete[1])
    core1_data_crc = crc(data[i])
    core1_code_crc = code_crc[i]
    rz = []
    for c, d in zip(code, data):
        b = zip_(c, pad=False) + zip_(d, pad=False)  # boot reads data right after the code stream
        rz.append(b + b"\0" * (-len(b) % 16))
    names = list(OVERLAYS)
    names[3], names[4] = names[4], names[3]
    rz[3], rz[4] = rz[4], rz[3]
    start = ovs[0].rom[0]
    if sym_mode:
        with open(out, "w") as f:
            o = start
            for n, b in zip(names, rz):
                f.write(f"boot_{n}_rzip_ROM_START = 0x{o:X};\nboot_{n}_rzip_ROM_END = 0x{o + len(b):X};\n")
                o += len(b)
        return 0
    end = start + sum(len(b) for b in rz)
    crcs = bytearray(0x20)
    for k, v in enumerate([*crc(boot_bytes), *core1_code_crc, *core1_data_crc]):
        crcs[4 * k:4 * k + 4] = v.to_bytes(4, "big")
    crc_rom = s["crc_ROM_START"]
    img = bytearray(rom[:boot.rom[0]]) + boot_bytes + crcs + rom[crc_rom + 0x20:start] + b"".join(rz)
    assert len(img) == end and end <= 0x1000000, hex(end)
    img += b"\xFF" * (0x1000000 - len(img))
    c1, c2 = cic_crc(img)
    img[0x10:0x18] = c1.to_bytes(4, "big") + c2.to_bytes(4, "big")
    open(out, "wb").write(img)
    print(f"{out}: code end {end:#x}, free {0x1000000 - end:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
