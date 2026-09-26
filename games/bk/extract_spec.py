"""DIRTY ROOM: US v1.1 ROM -> clean-room spec (kept facts only).

    python -m games.bk.extract_spec <v1.1 rom.z64> <spec dir>
Writes:
  kept_assets.bin + kept_assets.json   every asset (v1.1 order) decompressed, with all texture and
                                        palette bytes zeroed (geometry, display lists, animations,
                                        level setups, text, note sequences, demo inputs are kept facts)
  textures.json.gz                      per model texture / sprite frame: format, size, colour grid
                                        (4x4; 16x16 from 128 px), 2-bit alpha outline if alpha varies
Prints a one-screen summary.
"""
import gzip
import json
import os
import sys

import numpy as np

from cleanroom.decomp.spec import alpha2, grid
from games.bk import assetfs as A, formats as F
from games.bk.dirty_rom import assets_bin
from games.bk.texsheet import frames


def fact(rgba):
    h, w = rgba.shape[:2]
    n = 16 if max(w, h) >= 128 else 4
    d = {"w": w, "h": h, "grid": grid(rgba.astype(np.float32), n)}
    if (rgba[..., 3] < 250).any():
        d["alpha2"] = alpha2(rgba[..., 3])
    return d


def main(argv):
    rom = open(argv[1], "rb").read()
    out = argv[2]
    os.makedirs(out, exist_ok=True)
    es = A.parse(assets_bin(rom))
    tex = {}
    blob = bytearray()
    meta = []
    zeroed = 0
    for e in es:
        if e.data is None:
            meta.append({"uid": e.uid, "flags": e.flags, "c": int(e.compressed), "seg": e.seg, "off": None})
            continue
        d = bytearray(e.data)
        if e.kind == "model":
            for r in F.model_textures(e.data):
                tex[f"m{e.uid:x}.{r['i']}"] = dict(fact(F.decode_region(e.data, r)), fmt=r["fmt"], siz=r["siz"])
                a, n = r["region"]
                d[a:a + n] = bytes(n)
                if r["pal"]:
                    a, n = r["pal"]
                    d[a:a + n] = bytes(n)
                zeroed += 1
        elif e.kind == "sprite":
            rs = F.sprite_chunks(e.data)
            for f, img in frames(e).items():
                r0 = next(r for r in rs if r["frame"] == f)
                tex[f"s{e.uid:x}.{f}"] = dict(fact(img), fmt=r0["fmt"], siz=r0["siz"])
            for r in rs:
                for k in ("pix", "pal"):
                    if r[k]:
                        a, n = r[k]
                        d[a:a + n] = bytes(n)
                zeroed += 1
        meta.append({"uid": e.uid, "flags": e.flags, "c": int(e.compressed), "seg": e.seg,
                     "off": len(blob), "len": len(d), "kind": e.kind})
        blob += d
    open(os.path.join(out, "kept_assets.bin"), "wb").write(blob)
    json.dump(meta, open(os.path.join(out, "kept_assets.json"), "w"), separators=(",", ":"))
    with gzip.open(os.path.join(out, "textures.json.gz"), "wt") as f:
        json.dump(tex, f, separators=(",", ":"))
    print(f"assets {len(meta)} ({len(blob) / 1e6:.1f} MB kept, {zeroed} pixel regions zeroed); "
          f"texture facts {len(tex)} (model {sum(k[0] == 'm' for k in tex)}, sprite frames {sum(k[0] == 's' for k in tex)})")


if __name__ == "__main__":
    main(sys.argv)
