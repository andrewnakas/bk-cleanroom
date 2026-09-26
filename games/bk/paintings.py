"""Mad Monster Mansion's paintings (texture 1 of each framed-picture model, 64x64, stored with t up).

Character paintings are renders of the characters' own models with our textures; the scenic
ones are drawn from our own descriptions. Model hook for generate.MODEL_HOOKS.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from games.bk import formats as F, project as P

SS = 4


def _bg(size, top, bottom):
    h = size * SS
    t = np.linspace(0, 1, h)[:, None, None]
    img = (np.array(top)[None, None] * (1 - t) + np.array(bottom)[None, None] * t) * np.ones((1, h, 1))
    return Image.fromarray(img.astype(np.uint8), "RGB").convert("RGBA")


def _render_char(model_uid, crop, top, bottom, size=64):
    from games.bk import generate
    d = generate.clean_model(model_uid)
    tex = {r["i"]: F.decode_region(d, r) for r in F.model_textures(d)}
    fig = P.render3d(d, tex, size * SS, "front", crop)
    img = _bg(size, top, bottom)
    img.alpha_composite(Image.fromarray(fig, "RGBA"))
    return img


def tree_and_moon(size=64):
    img = _bg(size, (20, 25, 70), (60, 60, 110))
    d = ImageDraw.Draw(img)
    S = size * SS
    d.ellipse((S * 0.58, S * 0.08, S * 0.86, S * 0.36), fill=(245, 240, 200))
    d.rectangle((0, S * 0.82, S, S), fill=(30, 40, 30))
    d.polygon([(S * 0.30, S), (S * 0.36, S * 0.45), (S * 0.42, S)], fill=(25, 20, 18))
    for a, l in ((-40, 0.22), (-15, 0.28), (20, 0.25), (45, 0.2)):     # bare branches
        x0, y0 = S * 0.37, S * 0.55
        r = np.radians(a - 90)
        d.line((x0, y0, x0 + np.cos(r) * S * l, y0 + np.sin(r) * S * l), fill=(25, 20, 18), width=int(S * 0.025))
    return img


def tower(size=64):
    img = _bg(size, (15, 20, 50), (70, 50, 90))
    d = ImageDraw.Draw(img)
    S = size * SS
    for k in range(25):
        rng = np.random.default_rng(k)
        x, y = rng.random() * S, rng.random() * S * 0.5
        d.ellipse((x, y, x + 3, y + 3), fill=(230, 230, 200))
    d.rectangle((S * 0.38, S * 0.30, S * 0.62, S), fill=(40, 35, 45))
    d.polygon([(S * 0.34, S * 0.31), (S * 0.5, S * 0.06), (S * 0.66, S * 0.31)], fill=(55, 30, 45))
    d.rectangle((S * 0.46, S * 0.42, S * 0.54, S * 0.52), fill=(250, 210, 80))
    return img


def blackeye(size=64):
    img = _bg(size, (90, 40, 30), (40, 20, 20))
    d = ImageDraw.Draw(img)
    S = size * SS
    d.ellipse((S * 0.22, S * 0.22, S * 0.78, S * 0.86), fill=(225, 175, 130))
    d.polygon([(S * 0.12, S * 0.32), (S * 0.5, S * 0.05), (S * 0.88, S * 0.32)], fill=(30, 25, 25))
    d.ellipse((S * 0.34, S * 0.44, S * 0.46, S * 0.56), fill=(250, 250, 250))
    d.ellipse((S * 0.38, S * 0.47, S * 0.44, S * 0.54), fill=(20, 20, 20))
    d.ellipse((S * 0.54, S * 0.43, S * 0.68, S * 0.57), fill=(15, 15, 15))            # eye patch
    d.line((S * 0.2, S * 0.36, S * 0.8, S * 0.62), fill=(15, 15, 15), width=int(S * 0.02))
    d.arc((S * 0.38, S * 0.62, S * 0.64, S * 0.78), 20, 160, fill=(90, 30, 30), width=int(S * 0.025))
    return img


PAINTINGS = {
    0x522: lambda: _render_char(0x451, (0.38, 0.52, 0.62, 0.80), (70, 30, 90), (25, 10, 35)),       # Grunty
    0x52A: lambda: _render_char(0x3CB, (0.0, 0.0, 1.0, 1.0), (40, 70, 40), (15, 30, 15)),           # Teehees
    0x52B: lambda: _render_char(0x54A, (0.0, 0.0, 1.0, 1.0), (90, 60, 120), (40, 25, 60)),          # minion
    0x527: blackeye,
    0x528: tower,
    0x529: tree_and_moon,
}


def hook(uid, d):
    fn = PAINTINGS.get(uid)
    if fn is None:
        return None
    img = fn().resize((64, 64), Image.LANCZOS).filter(ImageFilter.SHARPEN).transpose(Image.FLIP_TOP_BOTTOM)
    return {1: np.asarray(img.convert("RGBA"), np.uint8)}
