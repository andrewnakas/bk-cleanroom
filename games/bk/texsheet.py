"""Dev tool: contact sheet of model textures / sprite frames from an assets.bin (dirty or clean).

    python -m games.bk.texsheet <assets.bin> <out.png> [--kind model|sprite] [--uids 0x2d1,0x2d2] [--start N] [--n 160]
Each tile: the texture scaled to fit 64x64 on a checkerboard, labelled uid.index.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

from games.bk import assetfs as A, formats as F


def frames(e):
    """Compose sprite chunks into frames."""
    rs = F.sprite_chunks(e.data)
    out = {}
    for r in rs:
        fw, fh = max(r["fw"], 1), max(r["fh"], 1)
        img = out.setdefault(r["frame"], np.zeros((fh, fw, 4), np.uint8))
        px = F.decode_region(e.data, r)
        x0, y0 = (0, 0) if len([q for q in rs if q["frame"] == r["frame"]]) == 1 else (r["x"], r["y"])
        h, w = px.shape[:2]
        ys, xs = slice(max(0, y0), min(fh, y0 + h)), slice(max(0, x0), min(fw, x0 + w))
        img[ys, xs] = px[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return out


def tiles(es, kind, uids, start, n):
    got = []
    for e in es:
        if e.data is None or e.kind != kind or (uids and e.uid not in uids):
            continue
        if kind == "model":
            for r in F.model_textures(e.data):
                got.append((f"{e.uid:x}.{r['i']}", F.decode_region(e.data, r)))
        else:
            for f, img in frames(e).items():
                got.append((f"{e.uid:x}.{f}", img))
    return got[start:start + n]


def sheet(items, out, cell=72):
    cols = 16
    rows = (len(items) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 10)), (40, 40, 40))
    dr = ImageDraw.Draw(im)
    for k, (lab, px) in enumerate(items):
        h, w = px.shape[:2]
        s = min(64 / w, 64 / h)
        t = Image.fromarray(px, "RGBA").resize((max(1, int(w * s)), max(1, int(h * s))), Image.NEAREST)
        bg = Image.new("RGBA", t.size, (200, 200, 200, 255))
        chk = np.indices(t.size[::-1]).sum(0) // 4 % 2
        bg = Image.fromarray(np.where(chk[..., None], 150, 210).astype(np.uint8).repeat(4, -1).reshape(t.size[1], t.size[0], 4))
        bg.putalpha(255)
        bg.alpha_composite(t)
        x, y = (k % cols) * cell, (k // cols) * (cell + 10)
        im.paste(bg.convert("RGB"), (x + 4, y + 2))
        dr.text((x + 2, y + cell - 4), lab, fill=(255, 255, 0))
    im.save(out)
    print(f"{len(items)} tiles -> {out}")


def main(argv):
    es = A.parse(open(argv[1], "rb").read())
    kind = argv[argv.index("--kind") + 1] if "--kind" in argv else "model"
    uids = {int(x, 16) for x in argv[argv.index("--uids") + 1].split(",")} if "--uids" in argv else None
    start = int(argv[argv.index("--start") + 1]) if "--start" in argv else 0
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 160
    sheet(tiles(es, kind, uids, start, n), argv[2])


if __name__ == "__main__":
    main(sys.argv)
