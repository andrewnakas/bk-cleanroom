"""CLEAN ROOM: build the clean ROM.

    python -m games.bk.make_clean <pristine decomp> <clean tree> <spec dir> [--skip-audio]
1. clean tree = the pristine decomp + tree_patches + spec/code (splat's linker script, hand-written
   asm, kept code bins: IPL3, RSP microcode). No retail asset data is involved.
2. assets.bin from the spec (generate.py), soundfonts from the spec (audio.py).
3. build_rom -> <clean>/build/us.v10/banjo.us.v10.z64
"""
import os
import shutil
import subprocess
import sys
import time

from games.bk import audio, generate

RETAIL = ["decompressed.us.v10.z64", "baserom.us.v10.z64", "assets.v11.bin", "assets.v10num.bin",
          "bin/assets.bin", "assets"]      # never present in a tree made from the pristine decomp


def make_tree(pristine, clean, spec):
    if not os.path.exists(os.path.join(clean, "Makefile")):
        shutil.copytree(pristine, clean, ignore=shutil.ignore_patterns(".git", "*.z64"), dirs_exist_ok=True)
    code = os.path.join(spec, "code")
    if not os.path.exists(code):
        code = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec", "code")
    shutil.copytree(code, clean, dirs_exist_ok=True)
    from games.bk import tree_patches
    tree_patches.apply(clean)
    for r in RETAIL:
        p = os.path.join(clean, r)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    for r in ["build/us.v10/assets.bin", "build/us.v10/bin/assets.bin.o"] + \
             [f"build/us.v10/bin/soundfont{n}{k}.bin.o" for n in (1, 2) for k in ("ctl", "tbl")]:
        p = os.path.join(clean, r)
        if os.path.exists(p):
            os.remove(p)


def main(argv):
    pristine, clean, spec = argv[1], argv[2], argv[3]
    t = time.time()
    make_tree(pristine, clean, spec)
    es = generate.build_entries(spec)
    out = generate.to_v10(es, spec)
    from games.bk import assetfs
    ab = os.path.join(clean, "assets.clean.bin")
    open(ab, "wb").write(assetfs.build(out))
    print(f"assets: {sum(e.data is not None for e in out)} ({time.time() - t:.0f}s)")
    if "--skip-audio" not in argv or not os.path.exists(os.path.join(clean, "bin/soundfont1tbl.bin")):
        for n in (1, 2):
            from games.bk import voices
            ctl, tbl = audio.build(spec, n, overrides=voices.override)
            open(os.path.join(clean, f"bin/soundfont{n}ctl.bin"), "wb").write(ctl)
            open(os.path.join(clean, f"bin/soundfont{n}tbl.bin"), "wb").write(tbl)
        print(f"audio: done ({time.time() - t:.0f}s)")
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/mips64/bin") + os.pathsep + env["PATH"]
    r = subprocess.run([sys.executable, "-m", "games.bk.build_rom", clean, ab, "--jobs", "8"], env=env,
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[-2:])
    print(f"make_clean: {time.time() - t:.0f}s")


if __name__ == "__main__":
    main(sys.argv)
