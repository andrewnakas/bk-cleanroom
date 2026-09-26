"""Re-typeset text: BK's sprite fonts and text-bearing textures, drawn with open fonts.

Fonts (one sprite frame, one chunk per glyph; the game indexes chunks by character;
chunk x/y are glyph metrics, kept):
  0x6EB  small dialog font, IA8, 13 px: chunk k = chr(0x21 + k) up to 'Z', then European letters
  0x6EC  large title/menu font, RGBA32, 23 px: ':' A..Z (c) (tm) ? ( ) < > " . ; - ! / '
Glyph cells keep the slot's size (a fact); the letters are drawn with Lilita One / Luckiest Guy.
Register with generate.HOOKS (done in generate.main via `import games.bk.drawn`).
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(__file__), "fonts")
SMALL = [chr(0x21 + k) for k in range(58)] + list("ÄÖÜßÀÂÇÉÈÊËÎÏÔÛÜÙ")
LARGE = [":"] + [chr(ord("A") + k) for k in range(26)] + ["©", "™", "?", "(", ")", "<", ">", '"', ".", ";", "-", "!", "/", "'"]


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def glyph_mask(ch, w, h, face, cap, base=None):
    """Alpha mask (h, w) float 0..1 of `ch`: font size set so capitals are `cap` px tall, baseline
    `base` px from the top (default: vertically centred capitals); squeezed horizontally only when
    the glyph is wider than the cell."""
    ss = 4
    f = _font(face, 10 * ss)
    hb = f.getbbox("H")
    size = int(round(10 * ss * cap * ss / max(1, hb[3] - hb[1])))
    f = _font(face, size)
    hb = f.getbbox("H")
    if base is None:
        base = (h + cap) / 2
    l, t, r, b = f.getbbox(ch)
    gw = max(1, r - l)
    im = Image.new("L", (gw + 8 * ss, h * ss + 8 * ss), 0)
    ImageDraw.Draw(im).text((4 * ss - l, int(base * ss) - hb[3] + 4 * ss), ch, font=f, fill=255)
    im = im.crop((0, 4 * ss, im.width, 4 * ss + h * ss))
    W = w * ss - 2 * ss
    if gw + 2 * ss > W:          # squeeze
        im = im.resize((max(1, W * im.width // (gw + 2 * ss)), im.height), Image.LANCZOS)
    out = Image.new("L", (w * ss, h * ss), 0)
    out.paste(im, ((w * ss - im.width) // 2, 0))
    return np.asarray(out.resize((w, h), Image.LANCZOS), np.float32) / 255.0


def small_font(key, fact, rgba):
    """IA8 glyphs: white letters, soft dark edge, transparent background."""
    cells = []
    for k, (x, y, w, h) in enumerate(fact["rects"]):
        if k >= len(SMALL):
            cells.append(np.zeros((h, w, 4), np.uint8))
            continue
        ch = SMALL[k]
        m = glyph_mask(ch, w, h, "LilitaOne-Regular.ttf", cap=9, base=11)
        # uniform cap height for letters/digits: fit on a reference glyph size
        edge = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)), np.float32) / 255
        a = np.maximum(m, edge * 0.8)
        lum = 60 + 195 * np.clip(m * 1.4, 0, 1)
        cells.append(np.dstack([lum, lum, lum, a * 255]).astype(np.uint8))
    return {"chunks": cells}


def large_font(key, fact, rgba):
    """RGBA32 glyphs: blue letters with a red drop edge (colours from the kept grid's style)."""
    cells = []
    fill = np.array([40, 60, 235], np.float32)
    shade = np.array([225, 30, 70], np.float32)
    for k, (x, y, w, h) in enumerate(fact["rects"]):
        if k >= len(LARGE):
            cells.append(np.zeros((h, w, 4), np.uint8))
            continue
        m = glyph_mask(LARGE[k], w - 1, h - 1, "LuckiestGuy-Regular.ttf", cap=18, base=20)
        mm = np.zeros((h, w), np.float32)
        sh = np.zeros((h, w), np.float32)
        mm[:h - 1, :w - 1] = m
        sh[1:, 1:] = m
        a = np.maximum(mm, sh)
        col = fill[None, None] * mm[..., None] + shade[None, None] * (sh * (1 - mm))[..., None]
        col = col / np.maximum(a, 1e-3)[..., None]
        cell = np.dstack([col, a * 255]).clip(0, 255).astype(np.uint8)
        cell[a < 0.06] = 0
        cells.append(cell)
    return {"chunks": cells}


SPRITES = {"s6eb.0": small_font, "s6ec.0": large_font}


def hook(key, fact, rgba):
    fn = SPRITES.get(key)
    return fn(key, fact, rgba) if fn else None
