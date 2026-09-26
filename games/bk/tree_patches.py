"""Build-tool patches for building the BK decomp natively on Windows (Git Bash).

    python -m games.bk.tree_patches <tree>
Each patch: (file, old, new). Idempotent (skips when `new` is already present).
Build with games/bk/bkenv.sh sourced and `make $BKMAKE`.
"""
import os
import sys

PATCHES = [
    # native Windows: the IDO recomp (Windows build) and libdragon binutils work fine
    ("Makefile",
     "ifeq ($(OS),Windows_NT)\n\t$(error Native Windows is currently unsupported for building this repository, use WSL instead c:)\nelse ifeq",
     "ifeq ($(OS),__never__)\nelse ifeq"),
    # ultralib: pass our cross prefix down
    ("Makefile",
     "$(MAKE) -C lib/ultralib VERSION=I TARGET=libultra_rom COMPARE=0 MODERN_LD=1 CC=",
     "$(MAKE) -C lib/ultralib VERSION=I TARGET=libultra_rom COMPARE=0 MODERN_LD=1 CROSS=$(CROSS) CC="),
    # python scripts are not directly executable on Windows
    ("lib/ultralib/Makefile", "\ttools/set_o32abi_bit.py", "\tpython tools/set_o32abi_bit.py"),
    # hand-written asm in core1: splat named the RNG seed by its v1.1 address (the v1.0 decomp
    # names that u64 sDebugVar_8027BEF0, "never used" by C: only this asm touches it)
    ("asm/core1/code_1E820.s", "D_80275CC0", "sDebugVar_8027BEF0"),
]


def apply(tree):
    n = 0
    for f, old, new in PATCHES:
        p = os.path.join(tree, f)
        s = open(p, newline="").read()
        if new in s and old not in s:
            continue
        assert old in s, f"patch target missing in {f}: {old[:40]!r}"
        open(p, "w", newline="").write(s.replace(old, new))
        n += 1
    print(f"tree_patches: {n} applied, {len(PATCHES) - n} already present")


if __name__ == "__main__":
    apply(sys.argv[1])
