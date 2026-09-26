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

## Works (2026-09-26 ~13:00)
- **Published**: repo https://github.com/andrewnakas/bk-cleanroom (public) + Pages https://andrewnakas.github.io/bk-cleanroom/ (gh-pages = site: EmulatorJS 4.2.3 + mupen64plus-next core with its ROM-DB entry "Banjo-Kazooie (U) (V1.0) [b1]" pointed at our ROM's MD5 for EEPROM 4 KB).
- **Clean ROM**: decomp v1.0 code + generated assets (4868 model textures, 1464 sprite frames: colour grid + detail + dither + alpha outline, our own CI palettes, mip chains) + resynthesised samples (467 wave tables, our own 4-predictor books). `games/bk/make_clean.py <pristine> <clean> games/bk/spec`.
- **Taint: 0 failing** (texture regions raw + decoded RGBA with a texel-aware low-information filter; PCM of both banks).
- Verified natively (mupen64plus, scripted input): N64 logo, Rare logo, intro, title, file select, Bottles/Tooty intro, Banjo's house, Spiral Mountain. Verified in headless Edge (GPU): boots through the intro.
- Dirty build (retail assets renumbered) also boots to the title: `games/bk/dirty_assets.py`.

## Hard-won facts
- v1.0 code + v1.1 table: v1.1 renumbered IDs (map in `spec/asset_renumber.json`, derived by `idmap.py`), and v1.1 emptied font slots 0x6E9/0x6EA that v1.0 loads; v1.0's `parallel_readDMA` turns a size-0 read into a runaway DMA (fills RAM). `generate.V10_FILL` fills them.
- Model texture list `size` counts from the list header (not the data start).
- The 1.9 TB D: drive dropped out for 80 s at ~05:45; the repo is pushed to GitHub since.
- Port 8097 is used by another session's server: use your own port for local tests.

## Done since publishing (2026-09-26 afternoon)
- Readable text: both sprite fonts re-typeset (Lilita One / Luckiest Guy, fitted to each glyph's advance width); title sign, copyright line, GAME OVER, THE END, PRESS START re-lettered in model space and baked into their tiles (`modelgeo.py`, `project.py`, `logos.py`).
- Faces: eye briefs for Banjo, Kazooie, the transformations, Tooty, Bottles, Jinjos, Klungo, Cheato, Grunty, Mumbo (`faces.py`).
- Pictures: 53 dialog portraits rendered from the characters' and objects' own models with our textures (`portraits.py`); 10 (Jiggy, bullion, feathers, egg pillow, a few bad name matches) keep the colour grid: their colours come from combiner prim/env colours, which the renderer does not model yet.
- Signs: level entry signs (9 worlds), ON VACATION, R.I.P., SKI-1000, Mumbo token numbers, the "BK" pole signs, the boot "RARE/WARE" plate.
- Renderer: lit models (G_LIGHTING) are shaded from their normals; Jiggy, bullion, feathers, egg pillow portraits now correct (57 of 61 portraits rendered).
- Paintings: Mad Monster Mansion portraits (Grunty, Teehees, minion rendered from models; Blackeye, tower, tree and moon drawn) (`paintings.py`).
- CI textures are bound at palette+pixels offset in display lists (`modelgeo.py`); needed for faces/portraits.
- Sprites: colour grids are alpha-weighted (brighter, correct HUD icon colours); I4/I8 sprites keep a 2-bit intensity outline (their shape).
- Voices: 96 placeholder lines (Piper TTS, pitched per character, fitted to the slot) for Banjo, Kazooie, Mumbo, Grunty, Bottles, Tooty, Jinjos, Cheato, Brentilda, Vile (`voices.py`, WAVs in `games/bk/voices`). Practice pack: `D:/n64work/bk/practice` (never publish).

## Next
1. Object portraits and item pictures with combiner colours (render prim/env colours).
2. Other text-bearing textures (R.I.P., ON VACATION, SKI-1000, note-door numbers, BK signs, level entry signs 0x563).
3. Mumbo token face, Jiggy picture, Rare intro logo (0x3A7).
4. Gameplay verified natively: holding the stick walks Banjo (play5.script: the script plugin counts controller polls, not frames).

## Browser testing notes
- Headless Edge: EmulatorJS pauses pages it thinks are hidden; `ports/ejs/cdp_shot.py` now pins visibility/focus. Speed in headless varies with GPU load from other sessions; the page is fine in a normal browser window.
- GitHub Pages legacy builds failed on a long gh-pages history of 16 MB ROMs: `tools/publish.sh` now pushes one orphan commit per deploy and requests a build.

## For the morning
- Play https://andrewnakas.github.io/bk-cleanroom/ in a real browser (Chrome/Edge). Keys: arrows, X jump, C attack, Z crouch, Enter start.
- Record voices: open `D:/n64work/bk/practice/SCRIPT.txt`; per character there is a call-and-response track (`BANJO.wav` etc.). Save each take as `games/bk/voices/<id>.wav`, then `python -m games.bk.make_clean D:/n64work/bk/pristine D:/n64work/bk/clean D:/n64work/bk/spec` and `sh tools/publish.sh`.
- Look at: title screen, dialog portraits, eyes in the intro close-ups.
