"""Check that our link puts every code/data object where the v1.0 yaml says (dev check).

    python -m games.bk.layout_check <tree>
Compares each yaml subsegment's ROM offset (as VRAM) with the address in build/us.v10/banjo.us.v10.map.
Prints the first drift per overlay and a count. A matching build has 0 drifts (assets excepted:
they are not in the code range).
"""
import re
import sys
from pathlib import Path


def main(argv):
    t = Path(argv[1])
    y = (t / "decompressed.us.v10.yaml").read_text().split("\n")
    mp = (t / "build/us.v10/banjo.us.v10.map").read_text().split("\n")
    addr = {}
    for l in mp:
        m = re.match(r"\s+(\.text|\.data|\.rodata|\.bss)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)", l)
        if m and int(m.group(3), 16):
            addr.setdefault((m.group(1), m.group(4)), int(m.group(2), 16))
    seg = None
    drifts = 0
    first = {}
    for l in y:
        m = re.match(r"- name:\s*(\S+)", l)
        if m:
            seg, rom0, vram0, d = m.group(1), None, None, None
            continue
        m = re.match(r"\s+start:\s*0x([0-9A-Fa-f]+)", l)
        if m and seg:
            rom0 = int(m.group(1), 16)
        m = re.match(r"\s+vram:\s*0x([0-9A-Fa-f]+)", l)
        if m and seg:
            vram0 = int(m.group(1), 16)
        m = re.match(r"\s+dir:\s*(\S+)", l)
        if m:
            d = m.group(1)
        m = re.match(r"\s+- \[0x([0-9A-Fa-f]+), ([\w.]+), ([^\],]+)(?:, ([^\],]+))?(?:, ([^\]]+))?\]", l)
        if not (m and seg and vram0):
            continue
        off, typ, name, a, b = int(m.group(1), 16), m.group(2), m.group(3).strip(), (m.group(4) or "").strip(), (m.group(5) or "").strip()
        dd = f"{d}/" if d else ""
        if typ == "c":
            key = (".text", f"build/us.v10/src/{dd}{name}.c.o")
        elif typ in (".data", ".rodata"):
            key = (typ, f"build/us.v10/src/{dd}{name}.c.o")
        elif typ == "hasm":
            key = (".text", f"build/us.v10/asm/{dd}{name}.s.o")
        elif typ == "lib":
            key = (b, f"build/us.v10/{a}.a({name}.o)")
        else:
            continue
        if key not in addr:
            continue
        exp = vram0 + off - rom0
        if addr[key] != exp:
            drifts += 1
            first.setdefault(seg, f"{key[1]} {key[0]}: yaml {exp:#x} ours {addr[key]:#x} ({addr[key] - exp:+#x})")
    print(f"layout drifts: {drifts}")
    for s, v in first.items():
        print(f"  {s}: first {v}")


if __name__ == "__main__":
    main(sys.argv)
