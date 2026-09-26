# Banjo-Kazooie clean room: status

## Decisions (log)
- 2026-09-25 22:40 ROM: `Banjo-Kazooie (USA) (Rev 1).z64`, SHA1 ded6ee16… = the decomp's `baserom.us.v11`. Unpacked to `D:/n64work/bk/rom/`.
- Decomp: n64decomp/banjo-kazooie @ 9db90a0 (100% matched), cloned LF to `D:/n64work/bk/pristine`.
- **The decomp only builds US v1.0** (and PAL). There is no v1.1 splat yaml or symbol file; the code has no v1.1 `#if` branches. We own a v1.1 cart, so:
  - **Code = decomp US v1.0** (all C). The web build is "v1.0 code + v1.1-derived assets".
  - `games/bk/dirty_rom.py` (dirty room) makes a v1.0-layout "decompressed" image for splat from the v1.1 ROM: header/IPL3/boot, soundfont ctl/tbl (same size in both, +0x35E0 in v1.1), the RSP microcode (end of core1 text/data), and 3 tiny hand-written asm files (bkmemops64, bkgetsr, code_1E820, found in v1.1 core1 by pattern). All C-code regions stay zero (unused: the C is compiled).
  - The asset filesystem is taken from v1.1 (3619 slots, same as v1.0's layout; 0x35D8 bytes bigger). The v1.0 code finds assets and soundfonts by linker symbols, so sizes can change.
  - `code_1E820.s` references the RNG seed by its v1.1 address; patched to `sDebugVar_8027BEF0` (`tree_patches.py`).
- **Web route = 3: clean ROM + WASM N64 emulator** (decided 23:00). Why: no BK PC port with a web target. Banjo: Recompiled needs RT64 (no web). The decomp builds a ROM. The MK64 session used EmulatorJS + mupen64plus_next with a core ROM-DB patch; I reuse that (`ports/ejs`).
- **Native Windows build, no make**: GNU make crashes parsing the decomp Makefile (access violation). `games/bk/build_rom.py` mirrors the Makefile and ultralib's ido.mk:
  - C: IDO 5.3 via the PW64 `idowin` passes (`tools/idowin/ido_cc.py`). The Windows `cc.exe` recomp has a cfe bug ("Unexpected End-of-file" on sins.c).
  - .s (ultralib): `~/.local/ido53/cc.exe` (as0/as1). Game .s: libdragon `mips64-elf-gcc`. Link: `mips64-elf-ld` with splat's `banjo.ld`.
  - The Rust `bk_asset_tool`/`bk_rom_compress` need a Unix-only C lib (rarezip). Replaced by `games/bk/assetfs.py` (asset FS parse/rebuild, raw deflate) and `games/bk/romtool.py` (overlay compression, anti-tamper CRC words, CIC-6103 checksum). Both are verified against retail: boot CRC and header CRC match.
  - Submodules must be LF too (`git submodule foreach 'git config core.autocrlf false; git rm --cached -r .; git reset --hard'`).
- **Kept as code** (not art): RSP microcode (F3DEX/L3DEX fifo, n_aspMain), IPL3 boot + font, hand-written asm. Same as MK64.

- **Compression must be Rare's own** (gzip 1.2.4 deflate): the game's inflate uses a fixed Huffman-table buffer at 0x803FBE00 and zlib streams crash `huft_build`. `tools/rarezip/rarezip.dll` = the decomp's rarezip C built with zig; `assetfs.zip_` reproduces all 3038 retail compressed assets byte-for-byte. Code+data streams of an overlay are packed with no gap (the boot reads data right after the code stream).
- **Asset numbering differs v1.0 vs v1.1**: v1.1 (like PAL) packs the dialog/quiz range that v1.0 spreads over 100-slot blocks; IDs < 0x8A3 agree, level models/midi are +0x7A2 in v1.0 (e.g. music base 0x1516 vs 0xD74). Plan: keep the decomp code unmodified and renumber the asset table into v1.0 IDs, with the map derived by aligning our v1.0 build against retail v1.1 code/data (`games/bk/idmap.py`, dirty room) plus the decomp's 299 `VER_SELECT(v1.0, PAL)` pairs. (A first try that used `VER_SELECT`'s PAL column failed: the PAL build is only partly matching; e.g. `mapModel.c` has no PAL IDs.)
- Debug tools: `tools/m64p_state.py` (mupen64plus.dll via ctypes: live PC/EPC/BadVAddr, RDRAM dump, libultra thread list with symbols), `games/bk/funcdiff.py` (our functions vs retail v1.1, relocations masked).

## Works
- **2026-09-26 01:10: dirty build boots to the title screen** (v1.0 decomp code + v1.1 assets renumbered to v1.0 IDs, `games/bk/renumber.py`, map in `spec/asset_renumber.json`): N64 logo, Rare logo, intro cutscene, title, PRESS START (native mupen64plus shots).
- v1.0's `parallel_readDMA` turns a size-0 read into a runaway DMA; v1.1 emptied font slot 0x6E9/0x6EA that v1.0 code loads (font 0). The asset builder must fill every empty slot the code can request (clean build: generated fonts).
- Dirty build: v1.0 code + v1.1 assets -> `build/us.v10/banjo.us.v10.z64` links and compresses (code end 0xFDD348).

## Next
- Boot test (native mupen64plus, `tools/m64p_test.py`).
- Census of assets (models' textures, sprites, midi, dialog), spec, generate, taint.

## For the morning
- (nothing yet)
