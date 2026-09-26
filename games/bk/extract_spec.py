"""DIRTY ROOM: US v1.1 ROM -> clean-room spec (kept facts only).

    python -m games.bk.extract_spec <v1.1 rom.z64> <spec dir>
Writes:
  kept_assets.bin + kept_assets.json   every asset (v1.1 order) decompressed, with all texture and
                                        palette bytes zeroed (geometry, display lists, animations,
                                        level setups, text, note sequences, demo inputs are kept facts)
  textures.json.gz                      per model texture / sprite frame: format, size, colour grid
                                        (4x4; 16x16 from 128 px; alpha-weighted), 2-bit alpha outline if alpha
                                        varies, 2-bit intensity outline for I4/I8 (their shape)
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


def agrid(rgba, n):
    """Colour grid weighted by alpha (transparent texels carry no colour); alpha is the plain mean."""
    h, w = rgba.shape[:2]
    f = rgba.astype(np.float64)
    a = f[..., 3:4] / 255.0
    tot = (f[..., :3] * a).reshape(-1, 3).sum(0) / max(a.sum(), 1e-6)
    out = []
    for gy in range(n):
        for gx in range(n):
            y0, y1 = gy * h // n, max(gy * h // n + 1, (gy + 1) * h // n)
            x0, x1 = gx * w // n, max(gx * w // n + 1, (gx + 1) * w // n)
            c, ca = f[y0:y1, x0:x1, :3], a[y0:y1, x0:x1]
            rgb = (c * ca).reshape(-1, 3).sum(0) / ca.sum() if ca.sum() > 0.5 else tot
            out.append([int(round(v)) for v in rgb] + [int(round(f[y0:y1, x0:x1, 3].mean()))])
    return out


def fact(rgba, fmt=None):
    h, w = rgba.shape[:2]
    n = 16 if max(w, h) >= 128 else 4
    d = {"w": w, "h": h, "grid": agrid(rgba, n)}
    if (rgba[..., 3] < 250).any():
        d["alpha2"] = alpha2(rgba[..., 3])
    if fmt == 4:          # intensity formats: the intensity pattern is the shape (drawn as alpha by the game)
        lum = rgba[..., :3].astype(np.float32) @ np.array([0.3, 0.59, 0.11], np.float32)
        d["ishape2"] = alpha2(lum.clip(0, 255).astype(np.uint8))
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
                tex[f"m{e.uid:x}.{r['i']}"] = dict(fact(F.decode_region(e.data, r), r["fmt"]), fmt=r["fmt"], siz=r["siz"])
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
                tex[f"s{e.uid:x}.{f}"] = dict(fact(img, r0["fmt"]), fmt=r0["fmt"], siz=r0["siz"])
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
