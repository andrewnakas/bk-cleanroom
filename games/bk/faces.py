"""Faces: eye textures painted from our own briefs (a colour grid alone turns eyes to mush).

BK eye textures are square: a big iris seen from the front on white, optionally an eyelid band
coming up from the bottom (blink states). A brief gives the style and lid height; iris and lid
colours are read from the kept 4x4 colour grid (the most saturated upper cell / the bottom row).

    brief = {"lid": 0..1, "style": "bk"|"ring"|"socket", "look": [dx, dy]}
"""
import colorsys

import numpy as np

SS = 4

# texture key (v1.1 uid.index) -> brief. Lid = fraction of the height the eyelid covers.
BRIEFS = {}


def _add(uid, specs):
    for i, b in specs.items():
        BRIEFS[f"m{uid:x}.{i}"] = b


OPEN, HALF, SHUT = {"lid": 0.0}, {"lid": 0.36}, {"lid": 0.58}
_add(0x34E, {14: HALF, 16: {"lid": 0.42}, 17: OPEN, 18: OPEN})          # Banjo & Kazooie (high poly)
_add(0x34D, {13: HALF, 15: {"lid": 0.42}, 16: OPEN, 17: OPEN})          # low poly
_add(0x34F, {2: OPEN, 5: HALF})                                          # termite
_add(0x359, {3: OPEN, 7: HALF})                                          # walrus
_add(0x362, {4: OPEN})                                                   # bee
_add(0x36F, {1: OPEN, 6: {"lid": 0.42}})                                 # pumpkin
_add(0x374, {1: OPEN, 6: {"lid": 0.45}})                                 # crocodile
_add(0x35B, {2: HALF, 3: OPEN})                                          # Tooty
_add(0x387, {0: {"lid": 0.3}, 1: OPEN})                                  # Bottles
for u in (0x3BB, 0x3BC, 0x3C0, 0x3C1, 0x3C2):                            # Jinjos
    _add(u, {0: {"lid": 0.28}, 1: OPEN, 3: SHUT})
_add(0x46A, {1: OPEN, 2: {"lid": 0.25}, 3: SHUT})                        # Klungo
_add(0x54F, {7: OPEN, 8: {"lid": 0.3}})                                  # Cheato
_add(0x451, {1: {"lid": 0.0, "style": "ring"}, 4: {"lid": 0.0, "style": "ring"}, 5: {"lid": 0.0, "style": "ring"}})
_add(0x3C6, {9: {"style": "socket"}})                                    # Mumbo's skull eye


def _colors(fact):
    g = np.asarray(fact["grid"], np.float32).reshape(4, 4, 4)
    cells = g[:2].reshape(-1, 4)          # top rows: never the eyelid
    def sat(c):
        h, l, s = colorsys.rgb_to_hls(*(c[:3] / 255))
        return s * (1 - abs(l - 0.5) * 1.2) + (0.15 if l < 0.35 else 0)
    iris = max(cells, key=sat)[:3]
    lidc = g[3].reshape(-1, 4)[:, :3].mean(0)
    return iris, lidc


def _ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2


def paint(brief, fact):
    w, h = fact["w"], fact["h"]
    W, H = w * SS, h * SS
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    x, y = (xs + 0.5) / W, (ys + 0.5) / H
    iris, lidc = _colors(fact)
    img = np.empty((H, W, 3), np.float32)
    img[:] = (248, 248, 244)
    style = brief.get("style", "bk")
    lx, ly = brief.get("look", [0.0, 0.0])
    cx, cy = 0.56 + lx, 0.52 + ly
    if style == "socket":
        img[:] = (25, 18, 14)
        r = _ell(x, y, 0.5, 0.5, 0.36, 0.36)
        img[(r <= 1) & (r > 0.55)] = np.clip(iris * 1.2, 0, 255)
        img[_ell(x, y, 0.5, 0.5, 0.14, 0.14) <= 1] = (235, 235, 245)
    else:
        rr = 0.44 if style == "bk" else 0.40
        r = _ell(x, y, cx, cy, rr, rr)
        dark = np.clip(iris * 0.45, 0, 255)
        img[r <= 1.0] = dark                                     # iris edge
        img[r <= 0.80] = iris
        img[(r <= 0.80) & (y < cy - 0.08)] = np.clip(iris * 1.25 + 20, 0, 255)   # lit upper iris
        pr = 0.21 if style == "bk" else 0.26
        img[_ell(x, y, cx + 0.02, cy + 0.04, pr, pr * 1.1) <= 1] = (12, 12, 16)   # pupil
        img[_ell(x, y, cx - 0.14, cy - 0.16, 0.085, 0.085) <= 1] = (255, 255, 255)
        img[_ell(x, y, cx + 0.12, cy + 0.14, 0.04, 0.04) <= 1] = (235, 235, 240)
    lid = brief.get("lid", 0.0)
    if lid > 0:
        top = 1.0 - lid
        edge = top + 0.05 * np.sin(np.pi * x)                    # slightly curved lid line
        img[y >= edge] = lidc
        img[(y >= edge - 0.035) & (y < edge + 0.005)] = np.clip(lidc * 0.4, 0, 255)
    out = img.reshape(h, SS, w, SS, 3).mean((1, 3))
    a = np.full((h, w), 255, np.float32)
    if "alpha2" in fact:
        from cleanroom.decomp.gen import unpack_alpha2
        a = unpack_alpha2(fact["alpha2"], w, h)
    return np.dstack([out, a]).clip(0, 255).astype(np.uint8)


def hook(key, fact, rgba):
    b = BRIEFS.get(key)
    return paint(b, fact) if b else None
