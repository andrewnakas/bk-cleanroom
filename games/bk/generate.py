"""CLEAN ROOM: spec -> clean assets.bin in v1.0 numbering (what the decomp's code expects).

    python -m games.bk.generate <spec dir> <out assets.bin> [--overrides dir]
For every model texture and sprite frame: pixels from the kept facts (colour grid + detail noise +
2-bit alpha outline), or from an override hook (drawn.py / text labels / briefs), encoded to the
slot's format; CI slots get our own palette. Mip tails are filled with a downsampled chain.
All other asset bytes come from the kept spec. Then the table is renumbered (renumber.py) and
compressed with Rare's compressor. Reads nothing from a ROM.
"""
import gzip
import json
import os
import sys

import numpy as np
from PIL import Image

from cleanroom.decomp.gen import from_digest
from cleanroom.gfx import texfmt as T
from games.bk import assetfs as A, formats as F, renumber as R

HOOKS = []          # functions (key, fact, rgba) -> rgba or None; registered by drawn.py etc.


def quantize(rgba, n):
    """Our own palette: -> (index array (h, w), palette (n, 4) uint8)."""
    h, w = rgba.shape[:2]
    a = rgba[..., 3]
    im = Image.fromarray(rgba, "RGBA")
    q = im.quantize(colors=n, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette("RGBA")[:4 * n] or [0] * 4 * n, np.uint8).reshape(-1, 4)
    pal = np.vstack([pal, np.zeros((n - len(pal), 4), np.uint8)])[:n]
    idx = np.array(q, np.uint8)
    pal[:, 3] = np.where(pal[:, 3] >= 128, 255, 0)
    return idx, pal


def encode(rgba, fmt, siz, pal_len=None):
    """-> (palette bytes or None, pixel bytes)"""
    if fmt == T.CI:
        n = 16 if siz == T.B4 else 256
        idx, pal = quantize(rgba, n)
        pix = T.encode(np.dstack([idx, idx, idx, idx]), T.CI, siz)
        return T.encode(pal[None, :, :], T.RGBA, T.B16), pix
    return None, T.encode(rgba, fmt, siz)


def mip_chain(rgba, fmt, siz, nbytes, pal_rgba=None):
    """Bytes for a mip tail: successive half-size levels, cut to nbytes."""
    out = bytearray()
    img = rgba
    while len(out) < nbytes:
        h, w = img.shape[:2]
        img = np.array(Image.fromarray(img, "RGBA").resize((max(1, w // 2), max(1, h // 2)), Image.BOX))
        if fmt == T.CI:
            n = len(pal_rgba)
            d = ((img[:, :, None, :].astype(int) - pal_rgba[None, None].astype(int)) ** 2).sum(-1)
            idx = d.argmin(-1).astype(np.uint8)
            out += T.encode(np.dstack([idx] * 4), T.CI, siz)
        else:
            out += T.encode(img, fmt, siz)
        if img.shape[0] == 1 and img.shape[1] == 1:
            out += bytes(nbytes)
    return bytes(out[:nbytes])


def dither(key, rgba, amp=10):
    """Per-texel noise so smooth areas never repeat retail texel runs after 5-bit quantisation."""
    from cleanroom.decomp.gen import h32
    rng = np.random.default_rng(h32("dither", key))
    n = rng.integers(-amp, amp + 1, rgba.shape[:2] + (1,))
    out = rgba.astype(np.int16)
    out[..., :3] += n
    return np.clip(out, 0, 255).astype(np.uint8)


def pixels(key, fact):
    rgba = from_digest(key, fact)
    if "ishape2" in fact:                     # intensity sprite: our own soft shape from the kept outline
        from cleanroom.decomp.gen import unpack_alpha2
        from PIL import ImageFilter
        v = unpack_alpha2(fact["ishape2"], fact["w"], fact["h"])
        v = np.asarray(Image.fromarray(v.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
        tint = rgba[..., :3].astype(np.float32).mean(-1, keepdims=True) / 255.0
        rgba = rgba.copy()
        rgba[..., :3] = np.clip(v[..., None] * (0.6 + 0.4 * tint) * 1.15, 0, 255).astype(np.uint8)
    for hook in HOOKS:
        r = hook(key, fact, rgba)
        if r is not None:
            return r if isinstance(r, dict) else np.asarray(r, np.uint8)
    return dither(key, rgba)


MODEL_HOOKS = []    # functions (uid, model bytes) -> {texture index: RGBA} or None (logos.py)


def gen_model(uid, d, facts):
    whole = {}
    for mh in MODEL_HOOKS:
        whole = mh(uid, bytes(d)) or {}
        if whole:
            break
    for r in F.model_textures(d):
        key = f"m{uid:x}.{r['i']}"
        fact = facts.get(key)
        if fact is None:
            continue
        rgba = whole[r["i"]] if r["i"] in whole else pixels(key, fact)
        pal, pix = encode(rgba, r["fmt"], r["siz"])
        if pal:
            a, n = r["pal"]
            d[a:a + n] = pal
        a, n = r["region"]
        d[a:a + len(pix)] = pix
        if n > len(pix):
            pr = T.decode(pal, len(pal) // 2, 1, T.RGBA, T.B16)[0] if pal else None
            d[a + len(pix):a + n] = mip_chain(rgba, r["fmt"], r["siz"], n - len(pix), pr)


def gen_sprite(uid, d, facts):
    rs = F.sprite_chunks(d)
    for f in sorted(set(r["frame"] for r in rs)):
        fr = [r for r in rs if r["frame"] == f]
        key = f"s{uid:x}.{f}"
        fact = facts.get(key)
        if fact is None:
            continue
        single = len(fr) == 1
        fact = dict(fact, rects=[(0, 0, r["w"], r["h"]) if single else (r["x"], r["y"], r["w"], r["h"]) for r in fr])
        img = pixels(key, fact)
        fmt, siz = fr[0]["fmt"], fr[0]["siz"]
        if isinstance(img, dict):                  # per-chunk images (fonts: one glyph per chunk)
            cells = [np.asarray(c, np.uint8) for c in img["chunks"]]
        else:
            fh, fw = img.shape[:2]
            cells = []
            for (x0, y0, w, h) in fact["rects"]:
                ys = np.clip(np.arange(y0, y0 + h), 0, fh - 1)
                xs = np.clip(np.arange(x0, x0 + w), 0, fw - 1)
                cells.append(img[ys][:, xs])
        if fmt == T.CI:
            strip = np.concatenate([c.reshape(-1, 4) for c in cells])[None]
            idx, pal_rgba = quantize(strip, 16 if siz == T.B4 else 256)
            a, n = fr[0]["pal"]
            d[a:a + n] = T.encode(pal_rgba[None], T.RGBA, T.B16)
            flat, o = idx[0], 0
        for r, c in zip(fr, cells):
            h, w = r["h"], r["w"]
            if fmt == T.CI:
                sub = flat[o:o + w * h].reshape(h, w)
                o += w * h
                b = T.encode(np.dstack([sub] * 4), T.CI, siz)
            else:
                b = T.encode(c, fmt, siz)
            a, n = r["pix"]
            d[a:a + n] = b[:n]


def load_spec(spec):
    meta = json.load(open(os.path.join(spec, "kept_assets.json")))
    kb = os.path.join(spec, "kept_assets.bin")
    blob = open(kb, "rb").read() if os.path.exists(kb) else gzip.open(kb + ".gz").read()
    with gzip.open(os.path.join(spec, "textures.json.gz"), "rt") as f:
        facts = json.load(f)
    return meta, blob, facts


SPEC = []


def clean_model(uid):
    """A model's clean bytes (textures generated), from the portrait cache or generated now."""
    from games.bk import portraits
    if uid not in portraits.CLEAN_MODELS:
        meta, blob, facts = SPEC
        m = next(x for x in meta if x["uid"] == uid)
        d = bytearray(blob[m["off"]:m["off"] + m["len"]])
        gen_model(uid, d, facts)
        portraits.CLEAN_MODELS[uid] = bytes(d)
    return portraits.CLEAN_MODELS[uid]


def register_hooks():
    if not HOOKS:
        from games.bk import faces, logos, paintings, portraits, text
        HOOKS.append(text.hook)
        HOOKS.append(faces.hook)
        HOOKS.append(portraits.hook)
        MODEL_HOOKS.append(logos.sign_textures)
        MODEL_HOOKS.append(paintings.hook)


def build_entries(spec):
    register_hooks()
    meta, blob, facts = load_spec(spec)
    from games.bk import logos
    logos.FACTS = facts
    SPEC[:] = [meta, blob, facts]
    es = []
    for m in meta:
        if m["off"] is None:
            es.append(A.Entry(m["uid"], m["seg"], bool(m["c"]), m["flags"], None))
            continue
        d = bytearray(blob[m["off"]:m["off"] + m["len"]])
        if m["kind"] == "model":
            gen_model(m["uid"], d, facts)
            from games.bk import portraits
            portraits.CLEAN_MODELS[m["uid"]] = bytes(d)
        elif m["kind"] == "sprite":
            gen_sprite(m["uid"], d, facts)
        es.append(A.Entry(m["uid"], m["seg"], bool(m["c"]), m["flags"], bytes(d)))
    return es


# v1.0 code asks for slots that v1.1 left empty (font 0 = 0x6E9 + font_id): fill with a generated font
V10_FILL = {0x6E9: 0x6EB, 0x6EA: 0x6EB}


def to_v10(es, spec):
    mp = {i: i for i in range(0x1000)}
    mp.update({int(k, 16): int(v, 16) for k, v in
               json.load(open(os.path.join(spec, "asset_renumber.json")))["v11_to_v10"].items()})
    out = R.apply(es, mp)
    for dst, src in V10_FILL.items():
        s = out[src]
        out[dst] = A.Entry(dst, s.seg, s.compressed, s.flags, s.data)
    return out


def main(argv):
    spec, dst = argv[1], argv[2]
    import time
    t = time.time()
    es = build_entries(spec)
    out = to_v10(es, spec)
    b = A.build(out)
    open(dst, "wb").write(b)
    print(f"generate: {sum(e.data is not None for e in out)} assets, {len(b) / 1e6:.2f} MB -> {dst} ({time.time() - t:.0f}s)")


if __name__ == "__main__":
    main(sys.argv)
