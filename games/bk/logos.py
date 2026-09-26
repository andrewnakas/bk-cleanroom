"""Title/overlay signs re-typeset in model space and baked back into their tiles (project.bake).

Each sign is a model whose 32x32 RGBA32 tiles are laid out by its own triangles. We draw our own
lettering (open fonts, our colours) over the sign's model-space box and bake it into the tiles.
Kept facts used: the geometry (box) and the words.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from games.bk import modelgeo as G, project as P
from games.bk.text import FONTS, _font

PX = 2.0      # canvas pixels per model unit


def _box(d):
    tb = G.tris_by_texture(d)
    pts = np.array([p[:2] for t in tb.values() for tri in t for p in tri[0]], np.float64)
    return pts.min(0), pts.max(0)


def _text_layer(size, text, face, px, fill, outline, ow, anchor_xy, rot=0.0, shadow=None):
    W, H = size
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = _font(face, px)
    l, t, r, b = f.getbbox(text)
    tmp = Image.new("RGBA", (r - l + 4 * ow + 8, b - t + 4 * ow + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    o = (2 * ow + 4 - l, 2 * ow + 4 - t)
    if shadow:
        d.text((o[0] + ow, o[1] + ow), text, font=f, fill=shadow, stroke_width=ow, stroke_fill=shadow)
    d.text(o, text, font=f, fill=fill, stroke_width=ow, stroke_fill=outline)
    if rot:
        tmp = tmp.rotate(rot, resample=Image.BICUBIC, expand=True)
    im.alpha_composite(tmp, (int(anchor_xy[0] - tmp.width / 2), int(anchor_xy[1] - tmp.height / 2)))
    return im


def _fit_px(text, face, max_w, max_h):
    px = int(max_h)
    while px > 6:
        l, t, r, b = _font(face, px).getbbox(text)
        if r - l <= max_w and b - t <= max_h:
            return px
        px -= 1
    return px


def word_art(W, H, lines, face="LuckiestGuy-Regular.ttf"):
    """lines: [(text, (cx, cy) in 0..1, height fraction, fill, outline, wobble)] -> RGBA image W x H."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for text, (cx, cy), hf, fill, outline, wob in lines:
        px = _fit_px(text, face, W * 0.96, H * hf)
        ow = max(2, px // 12)
        if wob:
            # bouncy letters: each letter its own slight rotation and lift
            f = _font(face, px)
            widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] + px * 0.06 for ch in text]
            total = sum(widths)
            x = cx * W - total / 2
            for k, ch in enumerate(text):
                lift = (px * 0.08) * (1 if k % 2 else -1)
                rot = 6 * (1 if (k * 7) % 3 else -1)
                im.alpha_composite(_text_layer((W, H), ch, face, px, fill, outline, ow,
                                               (x + widths[k] / 2, cy * H + lift), rot, shadow=(20, 20, 40, 200)))
                x += widths[k]
        else:
            im.alpha_composite(_text_layer((W, H), text, face, px, fill, outline, ow, (cx * W, cy * H),
                                           shadow=(20, 20, 40, 180)))
    return im


def canvas_fn(img, lo, hi):
    a = np.asarray(img, np.uint8)
    H, W = a.shape[:2]

    def fn(x, y):
        u = np.clip(((x - lo[0]) / (hi[0] - lo[0]) * (W - 1)).round().astype(int), 0, W - 1)
        v = np.clip(((hi[1] - y) / (hi[1] - lo[1]) * (H - 1)).round().astype(int), 0, H - 1)
        return a[v, u]
    return fn


ORANGE, ORANGE_D = (250, 130, 20, 255), (150, 50, 10, 255)
BLUE, RED, GOLD = (35, 70, 215, 255), (225, 35, 30, 255), (250, 200, 40, 255)
PURPLE, WHITE, INK = (80, 50, 220, 255), (245, 245, 245, 255), (30, 30, 30, 255)

SIGNS = {
    0x54C: [("GAME OVER", (0.5, 0.5), 0.8, ORANGE, ORANGE_D, True)],
    # the sign is tiled only where lettering sits: full rows from 25 % down, a left-middle bump above
    0x54D: [("BANJO-", (0.36, 0.37), 0.33, BLUE, GOLD, True), ("-KAZOOIE", (0.52, 0.72), 0.40, RED, GOLD, True),
            ("TM", (0.95, 0.33), 0.09, RED, GOLD, False)],
    0x54E: [("©1998 NINTENDO/RARE", (0.5, 0.28), 0.42, WHITE, INK, False),
            ("GAME BY RARE", (0.5, 0.76), 0.42, WHITE, INK, False)],
    0x56C: [("THE END", (0.5, 0.5), 0.8, PURPLE, ORANGE, True)],
}
PRESS_START = "PRESTA"     # 0x55C tiles 0..5, stored upside down like every sign tile


def sign_textures(uid, d):
    """-> {texture index: RGBA} or None."""
    if uid in SIGNS:
        lo, hi = _box(d)
        W, H = int((hi[0] - lo[0]) * PX), int((hi[1] - lo[1]) * PX)
        img = word_art(W, H, SIGNS[uid])
        return P.bake(d, canvas_fn(img, lo, hi))
    if uid == 0x55C:
        out = {}
        for i, ch in enumerate(PRESS_START):
            im = word_art(64, 64, [(ch, (0.5, 0.52), 0.86, WHITE, INK, False)], face="LilitaOne-Regular.ttf")
            im = im.resize((32, 32), Image.LANCZOS).transpose(Image.FLIP_TOP_BOTTOM)   # t runs upward
            out[i] = np.asarray(im, np.uint8)
        return out
    return None
