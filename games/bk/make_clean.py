"""CLEAN ROOM: build the clean ROM.

    python -m games.bk.make_clean <dirty tree> <clean tree> <spec dir> [--skip-audio]
1. clean tree = the dirty tree's code (decomp source, splat's linker script and hand-written asm,
   kept code bins: IPL3, RSP microcode) without any retail asset data (assets, soundfonts,
   decompressed/baseroms are removed).
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
          "bin/assets.bin", "bin/soundfont1ctl.bin", "bin/soundfont1tbl.bin", "bin/soundfont2ctl.bin",
          "bin/soundfont2tbl.bin", "assets"]


def make_tree(dirty, clean):
    if not os.path.exists(clean):
        shutil.copytree(dirty, clean, ignore=shutil.ignore_patterns("*.z64", "assets*.bin", "*.elf"))
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
    dirty, clean, spec = argv[1], argv[2], argv[3]
    t = time.time()
    make_tree(dirty, clean)
    es = generate.build_entries(spec)
    out = generate.to_v10(es, spec)
    from games.bk import assetfs
    ab = os.path.join(clean, "assets.clean.bin")
    open(ab, "wb").write(assetfs.build(out))
    print(f"assets: {sum(e.data is not None for e in out)} ({time.time() - t:.0f}s)")
    if "--skip-audio" not in argv or not os.path.exists(os.path.join(clean, "bin/soundfont1tbl.bin")):
        for n in (1, 2):
            ctl, tbl = audio.build(spec, n)
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
