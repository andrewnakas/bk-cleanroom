"""Build the BK decomp (us.v10 code) natively on Windows, without make.

    python -m games.bk.build_rom <tree> <assets.bin> [--jobs N]
Mirrors the decomp Makefile (and lib/ultralib's ido.mk) with the Windows IDO 5.3 recomp
(~/.local/ido53/cc.exe) and libdragon's mips64-elf binutils. Needs splat already run in <tree>.
Incremental: an object is rebuilt when older than its source. Output:
  <tree>/build/us.v10/banjo.us.v10.z64
"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
CC = str(HOME / ".local/ido53/cc.exe")          # .s files (as0/as1)
IDO_CC = [sys.executable, str(Path(__file__).resolve().parents[2] / "tools/idowin/ido_cc.py")]  # .c files
os.environ.setdefault("IDO_BIN", "C:/Users/andre/n64work/idowin/bin")
X = str(HOME / ".local/mips64/bin/mips64-elf-")
V = "us.v10"
B = f"build/{V}"

CFLAGS = ("-c -Wab,-r4300_mul -non_shared -G 0 -Xcpluscomm -D_FINALROM -DF3DEX_GBI -DVERSION=0 -DNDEBUG "
          "-DBUILD_VERSION=VERSION_I -DBKDIFFS -DANTI_TAMPER=1 -DANTI_PIRACY=1 -woff 649,654,838,807").split()
CPPFLAGS = "-D_FINALROM -DN_MICRO -DNDEBUG -DBUILD_VERSION=VERSION_I -DBKDIFFS".split()
INCS = ("-I . -I include -I lib/ultralib/include -I lib/ultralib/include/PR -I lib/ultralib/include/PRinternal "
        "-I lib/ultralib/include/compiler/ido -I include/n_audio/PR -I lib/ultralib/src/audio").split()
GCC_AS = ("-c -x assembler-with-cpp -Wa,-Iinclude -mabi=32 -ffreestanding -mtune=vr4300 -march=vr4300 -mfix4300 "
          "-G 0 -O -mno-shared -fno-PIC -mno-abicalls").split()

U_CFLAGS = "-c -Wab,-r4300_mul -G 0 -nostdinc -Xcpluscomm -fullwarn -woff 516,649,838,712".split()
U_ASFLAGS = "-c -Wab,-r4300_mul -G 0 -nostdinc -woff 516,649,838,712".split()


def run(cmd, cwd):
    # forward slashes: IDO's cfe reads "\n" in "D:\n64work" as an escape
    cmd = [str(c).replace("\\", "/") for c in cmd]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    return r


def stale(out, *srcs):
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        return True
    t = os.path.getmtime(out)
    return any(os.path.getmtime(s) > t for s in srcs)


def ultralib_jobs(tree):
    u = tree / "lib/ultralib"
    names = (u / "base/I/libultra_rom.txt").read_text().split()
    srcs = {}
    for p in sorted((u / "src").rglob("*")):
        if p.suffix not in (".c", ".s"):
            continue
        rel = p.relative_to(u).as_posix()
        if p.suffix == ".s" and rel.startswith("src/mgu/") and p.stem in ("mtxcatf", "normalize", "scale", "translate"):
            continue
        srcs.setdefault(p.stem.lower() + ".o", p)
    jobs, order = [], []
    for n in names:
        p = srcs.get(n.lower())
        if p is None:
            continue
        rel = p.relative_to(u).as_posix()
        d = rel.split("/")[1]
        out = tree / B / "ultralib" / (p.stem + ".o")  # member names as in banjo.ld
        order.append(out)
        gbi = {"parse_gbi": ["-DF3D_GBI"], "sprite": ["-DF3D_GBI"], "us2dex_emu": [], "us2dex2_emu": [],
               "spriteex": [], "spriteex2": []}.get(p.stem, ["-DF3DEX_GBI"])
        mips = ["-mips2", "-o32"]
        pic = ["-non_shared"]
        if p.stem in ("ll", "llbit", "llcvt") and d == "libc" or rel == "src/os/exceptasm.s":
            mips = ["-mips3", "-32"]
        if rel == "src/log/delay.c":
            mips, pic = ["-mips1", "-o32"], ["-KPIC"]
        cpp = ["-D_MIPS_SZLONG=32"] + gbi + ["-DBUILD_VERSION=VERSION_I"] + pic + \
              ["-DNDEBUG", "-D_FINALROM"]
        iinc = ["-I", str(u / "include"), "-I", str(u / "include/compiler/ido"), "-I", str(u / "include/PR")]
        if p.suffix == ".c":
            opt = "-O1"
            if d in ("libc", "sched", "gu", "mgu", "sp", "audio", "rg", "gt"):
                opt = "-O3"
            if d in ("debug", "host", "os", "rmon", "log"):
                opt = "-O1"
            if rel in ("src/libc/ll.c", "src/libc/llbit.c", "src/libc/llcvt.c", "src/libc/syncprintf.c"):
                opt = "-O1"
            if rel == "src/os/initialize_isv.c":
                opt = "-O2"
            cmd = IDO_CC + U_CFLAGS + mips + cpp + [opt] + iinc + ["-o", str(out), p.name]
        else:
            opt = "-O2" if d in ("libc", "mgu") or rel == "src/os/exceptasm.s" else "-O1"
            cmd = [CC] + U_ASFLAGS + mips + cpp + [opt, p.name] + iinc + ["-o", str(out)]
        post = [["python", str(u / "tools/set_o32abi_bit.py"), str(out)],
                [X + "strip", str(out), "-N", "asdasdasdasd"],
                [X + "objcopy", "--remove-section", ".mdebug", str(out)]]
        jobs.append((out, [p], [(cmd, p.parent)] + [(c, tree) for c in post]))
    return jobs, order


def game_jobs(tree):
    jobs = []
    for p in sorted((tree / "src").rglob("*.c")):
        rel = p.relative_to(tree).as_posix()
        out = tree / B / (rel + ".o")
        opt = "-O3" if rel.startswith(("src/core1/ultra/audio/", "src/core1/n_audio/")) else "-O2"
        cmd = IDO_CC + CFLAGS + CPPFLAGS + INCS + [opt, "-mips2", "-o", str(out), rel]
        steps = [(cmd, tree)]
        if rel.startswith("src/boot/"):
            steps += [([X + "strip", str(out), "-N", "asdasdasasdasd"], tree),
                      ([X + "objcopy", "--prefix-symbols=boot_", str(out)], tree),
                      ([X + "objcopy", "--strip-unneeded", str(out)], tree)]
        jobs.append((out, [p], steps))
    for p in sorted((tree / "asm").rglob("*.s")):
        rel = p.relative_to(tree).as_posix()
        if "/nonmatchings/" in rel:
            continue
        out = tree / B / (rel + ".o")
        steps = [([X + "gcc"] + GCC_AS + INCS + ["-o", str(out), rel], tree)]
        if not rel.startswith(("asm/core1/", "asm/data/core1/")):
            steps.append(([X + "objcopy", "--prefix-symbols=boot_", str(out)], tree))
        jobs.append((out, [p], steps))
    for p in sorted((tree / "bin").rglob("*.bin")):
        rel = p.relative_to(tree).as_posix()
        if rel == "bin/assets.bin":
            continue
        out = tree / B / (rel[:-4] + ".bin.o")
        jobs.append((out, [p], [([X + "ld", "-r", "-b", "binary", "-o", str(out), rel], tree)]))
    return jobs


def do(job):
    out, srcs, steps = job
    if not stale(out, *srcs):
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    for cmd, cwd in steps:
        run(cmd, cwd)
    return 1


def main(argv):
    tree = Path(argv[1]).resolve()
    assets = Path(argv[2]).resolve()
    jobs_n = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 6
    ujobs, uorder = ultralib_jobs(tree)
    gjobs = game_jobs(tree)
    built, errs = 0, []
    with ThreadPoolExecutor(jobs_n) as ex:
        for f in [ex.submit(do, j) for j in ujobs + gjobs]:
            try:
                built += f.result()
            except RuntimeError as e:
                errs.append(str(e))
    print(f"objects: {len(ujobs)} ultralib + {len(gjobs)} game, rebuilt {built}, failed {len(errs)}")
    if errs:
        for e in errs[:5]:
            print(e[:1500])
        return 1
    b = tree / B
    lib = b / "libultra_rom.a"
    if built or not lib.exists():
        lib.unlink(missing_ok=True)
        run([X + "ar", "rcs", str(lib)] + [str(o) for o in uorder], tree)
        bl = b / "libultra_rom_boot.a"
        run([X + "objcopy", "--prefix-symbols=boot_", str(lib), str(bl)], tree)
    # assets
    ab = b / "assets.bin"
    if stale(ab, assets):
        ab.write_bytes(assets.read_bytes())
    ao = b / "bin/assets.bin.o"
    ao.parent.mkdir(parents=True, exist_ok=True)
    if stale(ao, ab):
        run([X + "ld", "-r", "-b", "binary", "-o", str(ao), f"{B}/assets.bin"], tree)
    ld = [X + "ld", "-T", "banjo.ld", "--no-check-sections", "--accept-unknown-input-arch",
          "-T", f"manual_syms.{V}.txt"]
    libs = [f"{B}/libultra_rom.a", f"{B}/libultra_rom_boot.a"]
    pre = f"{B}/banjo.{V}.prelim"
    run(ld + ["-Map", pre + ".map", "-T", f"rzip_dummy_addrs.{V}.txt"] + libs + ["-o", pre + ".elf"], tree)
    run([X + "objcopy", pre + ".elf", pre + ".z64", "-O", "binary"], tree)
    py = [sys.executable, "-m", "games.bk.romtool"]
    here = Path(__file__).resolve().parents[2]
    sym = f"{B}/compressed_symbols.txt"
    subprocess.run(py + ["--symbols", str(tree / (pre + ".elf")), str(tree / (pre + ".z64")), str(tree / sym)],
                   cwd=here, check=True)
    fin = f"{B}/banjo.{V}"
    run(ld + ["-Map", fin + ".map", "-T", sym] + libs + ["-o", fin + ".elf"], tree)
    run([X + "objcopy", fin + ".elf", fin + ".uncompressed.z64", "-O", "binary"], tree)
    subprocess.run(py + [str(tree / (fin + ".elf")), str(tree / (fin + ".uncompressed.z64")), str(tree / (fin + ".z64"))],
                   cwd=here, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
