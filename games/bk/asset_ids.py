"""Source patch: build the US v1.0 code against the v1.1 asset table numbering.

US v1.1 (and PAL) pack the dialog/quiz blocks that v1.0 spreads over 100-slot groups, so every
asset ID from 0x8A3 up differs between v1.0 and v1.1. The decomp matches PAL too, so each such ID
is already written as VER_SELECT(v1.0, PAL, ...) (or an #if VERSION block); v1.1 uses the PAL
numbering (checked: v1.1 slot 0x9C9 is Croctus's text, PAL ID 0x9C9 in croctus.c, etc.).

    python -m games.bk.asset_ids <tree>
Rewrites asset-ID VER_SELECT(...) calls to VER_ASSET(...) (= the PAL column) and the music base.
Idempotent; prints counts.
"""
import re
import sys
from pathlib import Path

VS = re.compile(r"VER_SELECT\(\s*(ASSET_\w+|0x[0-9A-Fa-f]+)\s*,\s*(ASSET_\w+|0x[0-9A-Fa-f]+)\s*,")
MACRO = """
/* clean-room web build: v1.0 code, v1.1 asset table (= PAL numbering) */
#define VER_ASSET(usa0, pal, usa1, jp) pal
"""
EXTRA = [("src/core1/code_11AC0.c", "#define MUSIC_TRACK_ASSET_BASE_ID   0x1516",
          "#define MUSIC_TRACK_ASSET_BASE_ID   0xD74 /* v1.1 table (PAL numbering) */")]


def is_asset(a, b):
    if a.startswith("ASSET_"):
        return True
    if a.startswith("0x") and b.startswith("0x"):
        return 0x800 <= int(a, 16) <= 0x1700 and 0x800 <= int(b, 16) <= 0x1700
    return False


def apply(tree):
    tree = Path(tree)
    vh = tree / "include/version.h"
    s = vh.read_text()
    if "VER_ASSET" not in s:
        s = s.replace("#endif // __BANJO_KAZOOIE_VERSION_H__", MACRO + "\n#endif // __BANJO_KAZOOIE_VERSION_H__")
        vh.write_text(s, newline="\n")
    n_files = n_sites = 0
    for p in list((tree / "src").rglob("*.c")) + list((tree / "include").rglob("*.h")):
        s = p.read_text(encoding="latin1")
        if "VER_SELECT" not in s:
            continue
        cnt = [0]

        def sub(m):
            if is_asset(m.group(1), m.group(2)):
                cnt[0] += 1
                return m.group(0).replace("VER_SELECT", "VER_ASSET", 1)
            return m.group(0)
        t = VS.sub(sub, s)
        if cnt[0]:
            p.write_text(t, encoding="latin1", newline="\n")
            n_files += 1
            n_sites += cnt[0]
    for f, old, new in EXTRA:
        p = tree / f
        s = p.read_text(encoding="latin1")
        if old in s:
            p.write_text(s.replace(old, new), encoding="latin1", newline="\n")
            n_sites += 1
    left = sum(len(re.findall(r"VER_SELECT\(\s*ASSET_", p.read_text(encoding="latin1")))
               for p in (tree / "src").rglob("*.c"))
    print(f"asset_ids: {n_sites} sites in {n_files} files -> PAL/v1.1 numbering; ASSET_ VER_SELECT left: {left}")


if __name__ == "__main__":
    apply(sys.argv[1])
