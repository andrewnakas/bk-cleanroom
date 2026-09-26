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


def _box(d, only=None):
    tb = G.tris_by_texture(d)
    if only is not None:
        tb = {k: v for k, v in tb.items() if k in only}
    pts = np.array([p[:2] for t in tb.values() for tri in t for p in tri[0]], np.float64)
    if not len(pts):
        return None, None
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


# signs made of a few tiles on a coloured board: uid -> [(texture indices, lines, fill, outline)]
# lines: [(text, (cx, cy), height fraction)]; the board colour is the tiles' kept grid colour.
YEL, DARK, CREAM = (250, 215, 60, 255), (40, 25, 10, 255), (240, 235, 210, 255)
BOARD_SIGNS = {
    0x563: [((0, 1), [("MUMBO'S", (0.5, 0.3), 0.36), ("MOUNTAIN", (0.5, 0.72), 0.36)], YEL, DARK),
            ((2, 3), [("TREASURE", (0.5, 0.3), 0.36), ("TROVE COVE", (0.5, 0.72), 0.36)], YEL, DARK),
            ((4, 5), [("CLANKER'S", (0.5, 0.3), 0.36), ("CAVERN", (0.5, 0.72), 0.36)], CREAM, DARK),
            ((6, 7), [("BUBBLEGLOOP", (0.5, 0.3), 0.36), ("SWAMP", (0.5, 0.72), 0.36)], CREAM, DARK),
            ((8, 9), [("FREEZEEZY", (0.5, 0.3), 0.36), ("PEAK", (0.5, 0.72), 0.36)], CREAM, DARK),
            ((10, 11), [("GOBI'S", (0.5, 0.3), 0.36), ("VALLEY", (0.5, 0.72), 0.36)], YEL, DARK),
            ((12, 13), [("MAD MONSTER", (0.5, 0.3), 0.36), ("MANSION", (0.5, 0.72), 0.36)], CREAM, DARK),
            ((14, 15), [("RUSTY", (0.5, 0.3), 0.36), ("BUCKET BAY", (0.5, 0.72), 0.36)], CREAM, DARK),
            ((16, 17), [("CLICK CLOCK", (0.5, 0.3), 0.36), ("WOOD", (0.5, 0.72), 0.36)], CREAM, DARK)],
    0x3A7: [((0, 1, 2, 3, 4, 5), [("RARE", (0.5, 0.36), 0.30), ("WARE", (0.5, 0.66), 0.22)],
             (250, 200, 60, 255), (60, 30, 10, 255))],                       # boot logo plate (frame = tile 6)
    0x2EE: [((1, 2), [("ON VACATION", (0.5, 0.5), 0.7)], (230, 40, 30, 255), CREAM)],
    0x3C9: [((0,), [("R.I.P.", (0.5, 0.62), 0.3)], (35, 35, 40, 255), (150, 150, 155, 255))],
    0x370: [((10,), [("SKI-1000", (0.5, 0.5), 0.6)], (40, 60, 200, 255), CREAM)],
    0x2F5: [((0,), [("BK", (0.5, 0.5), 0.55)], (40, 60, 220, 255), (250, 250, 250, 255))],
    0x2F6: [((0,), [("BK", (0.5, 0.5), 0.55)], (230, 40, 40, 255), (250, 250, 250, 255))],
    0x2F9: [((0,), [("BK", (0.5, 0.5), 0.55)], (40, 60, 220, 255), (250, 250, 250, 255))],
}
for _k, _n in zip(range(0x301, 0x306), ("5", "10", "15", "20", "25")):     # Mumbo token signs
    BOARD_SIGNS[_k] = [((0,), [(_n, (0.5, 0.3), 0.45)], (230, 40, 40, 255), (40, 60, 220, 255))]
FACTS = {}     # set by generate: texture key -> fact
TEXSPACE = {0x2F5: False, 0x2F6: False, 0x2F9: False}   # wrapped on 3D shapes: draw in texture space (value: flip)


def _board(uid, idx, W, H):
    """Our own board: the tiles' mean kept colour with soft horizontal grain."""
    g = []
    for i in idx:
        f = FACTS.get(f"m{uid:x}.{i}")
        if f:
            g += [c for c in f["grid"] if c[3] > 128]
    col = np.array(np.mean(g, 0)[:3] if g else (120, 90, 50), np.float32)
    rng = np.random.default_rng(uid * 97 + idx[0])
    grain = np.repeat(rng.normal(0, 1, (H, 1)), W, 1)
    grain = np.convolve(grain[:, 0], np.ones(5) / 5, "same")[:, None] * np.ones((1, W))
    img = np.clip(col[None, None] * (1 + 0.08 * grain[..., None]), 0, 255)
    return Image.fromarray(np.dstack([img, np.full((H, W), 255)]).astype(np.uint8), "RGBA")


def board_signs(uid, d):
    out = {}
    from games.bk import formats as F
    rs = {r["i"]: r for r in F.model_textures(d)}
    for idx, lines, fill, outline in BOARD_SIGNS[uid]:
        lo, hi = _box(d, set(idx))
        flat = lo is None or not np.all(hi - lo > 4) or uid in TEXSPACE
        if flat:
            # not laid out in the XY plane: draw in texture space, tiles side by side, t running upward
            W = sum(rs[i]["w"] for i in idx) * 4
            H = rs[idx[0]]["h"] * 4
            img = _board(uid, idx, W, H)
            img.alpha_composite(word_art(W, H, [(t, c, hf, fill, outline, False) for t, c, hf in lines],
                                         face="LilitaOne-Regular.ttf"))
            if TEXSPACE.get(uid, True):
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            x = 0
            for i in idx:
                w = rs[i]["w"] * 4
                out[i] = np.asarray(img.crop((x, 0, x + w, H)).resize((rs[i]["w"], rs[i]["h"]), Image.LANCZOS), np.uint8)
                x += w
            continue
        W, H = int((hi[0] - lo[0]) * PX), int((hi[1] - lo[1]) * PX)
        img = _board(uid, idx, W, H)
        img.alpha_composite(word_art(W, H, [(t, c, hf, fill, outline, False) for t, c, hf in lines],
                                     face="LilitaOne-Regular.ttf"))
        out.update(P.bake(d, canvas_fn(img, lo, hi), only=set(idx)))
    return out


def sign_textures(uid, d):
    """-> {texture index: RGBA} or None."""
    if uid in BOARD_SIGNS:
        return board_signs(uid, d) or None
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
