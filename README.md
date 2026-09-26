# Banjo-Kazooie — clean room web build

Play: **https://andrewnakas.github.io/bk-cleanroom/**

Banjo-Kazooie built from the [n64decomp/banjo-kazooie](https://github.com/n64decomp/banjo-kazooie)
decompilation, with **every texture, sprite and sound sample regenerated** (no retail pixels or
samples), running in the browser with EmulatorJS (mupen64plus-next). No ROM is needed to play.

Controls: **Arrows** move · **X** A (jump) · **C** B (attack) · **Z** Z (crouch) · **S** R (camera) ·
**Q** L · **Enter** Start · **I J K L** C-buttons. Gamepads work too. Saves stay in your browser.

## What is kept, what is generated

The decomp is the game's code as C. Banjo-Kazooie's content lives in an asset filesystem in the
ROM (3619 files). The project reads a ROM **once, in a "dirty room" step** (`extract_spec.py`,
`audio.py spec`), keeps only the facts below, and builds everything else:

| Asset | Kept fact | Generated |
|---|---|---|
| Model textures (4868) and sprite frames (1464) | format, size, a 4×4 colour grid (16×16 from 128 px), a 2-bit alpha outline | colour from the grid, our own noise and dither, our own CI palettes, mip chains |
| Geometry, display lists, collision, animations, level setups | kept (as geometry is in other decomps) | — |
| Dialog text, quiz questions | kept (the words) | — |
| Music (compact MIDI sequences) | note events | played by the resynthesised instruments |
| Sound samples (467 wave tables, 2 banks) | length, loop points, a coarse spectral outline, median pitch; bank structure (envelopes, key maps, tuning) | resynthesised; our own 4-predictor VADPCM books |
| RSP microcode, IPL3 boot code, 3 small hand-written asm files | kept as code | — |

`games/bk/taint_report.py` compares every generated texture region (raw and decoded, texel-aware)
and every sample against the retail data for shared runs of 32 bytes or more: **0 failing**.

## Version notes (why this is v1.0 code with v1.1-derived facts)

- The decomp builds US v1.0; the ROM used for the facts is US v1.1. `dirty_rom.py` builds the
  v1.0-layout image splat needs from v1.1 (only non-C segments matter; all code is compiled).
- v1.1 renumbered the asset table (packed dialog blocks, shifted level models and music). The
  v1.0 code is kept unmodified; `renumber.py` maps the kept assets into v1.0 IDs. The map comes
  from aligning our v1.0 build with v1.1 code and data (`idmap.py`) plus the decomp's
  `VER_SELECT(v1.0, PAL, …)` pairs (315/316 agree).
- The game's inflate has a fixed-size Huffman table, so everything is compressed with Rare's own
  gzip-1.2.4-based compressor (`tools/rarezip`, built from the decomp's rarezip tool); it
  reproduces the retail compressed assets byte for byte.

## Build (Windows, Git Bash, no WSL)

Needs Python 3.12 (numpy, Pillow, scipy), the IDO 5.3 passes (`tools/idowin`), libdragon's
`mips64-elf` binutils, and a clone of the decomp (`git clone -c core.autocrlf=false ...`, submodules LF).

```sh
# clean room (from this repo's spec; no ROM)
python -m games.bk.make_clean <decomp clone> <clean tree> games/bk/spec
python ports/ejs/patch_core.py <clean tree>/build/us.v10/banjo.us.v10.z64 <ejs>/data/cores cores
python ports/ejs/make_site.py <clean tree>/build/us.v10/banjo.us.v10.z64 <emulatorjs> site

# dirty room (once, your own US v1.1 ROM; outputs never published)
python -m games.bk.dirty_rom rom.z64 <dirty tree>          # v1.0-layout image for splat
python -m games.bk.extract_spec rom.z64 <spec>             # kept facts
python -m games.bk.audio spec <dirty tree> <spec>
python -m games.bk.taint_report rom.z64 <dirty tree> <clean>/assets.clean.bin <clean tree>
```

`build_rom.py` replaces the decomp's Makefile on Windows; `romtool.py` and `assetfs.py` replace
its Rust tools. Dev tools: `tools/m64p_test.py` (native screenshots, scripted input),
`tools/m64p_state.py` (live PC/threads/RDRAM), `games/bk/funcdiff.py`, `ports/ejs/cdp_shot.py`.

## Legal note

This repository contains no ROM. It contains the kept facts listed above (in `games/bk/spec`).
All textures, sprites and samples are generated. The game code is the community decompilation.
Banjo-Kazooie is a trademark of Microsoft/Rare; Nintendo 64 is a trademark of Nintendo. This
project is not affiliated with either. EmulatorJS (GPL-3.0) and mupen64plus-next (GPL-2.0) are
vendored in the site; see `THIRD_PARTY.md` there.
