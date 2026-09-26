"""Dialog portraits (and item pictures) rendered from the game's own models with our textures.

Portrait sprites 0x7EF..0x849 (32x32 CI4, 10 talking frames) show the speaker's head or the item.
We render the matching model (bind pose, z-buffered, front view) with the clean textures, crop the
head (fractions of the model's extent, y up), and use the picture for every frame (frames alternate
a slight bob so the talking animation still moves).

    PORTRAITS: v1.1 sprite uid -> (model uid, view, crop)
build(clean model textures) is called by generate once the model textures exist.
"""
import numpy as np
from PIL import Image

from games.bk import formats as F, project as P

HEAD = (0.32, 0.58, 0.68, 1.0)
WHOLE = (0.0, 0.0, 1.0, 1.0)

PORTRAITS = {
    0x7EF: (0x34E, "front", (0.36, 0.62, 0.64, 0.93)),       # Banjo
    0x7F4: (0x34E, "back", (0.38, 0.74, 0.62, 1.0)),        # Kazooie (behind Banjo)
    0x7F0: (0x387, "front", (0.30, 0.50, 0.70, 1.0)),        # Bottles
    0x7FC: (0x3C6, "front", (0.28, 0.45, 0.72, 0.92)),       # Mumbo
    0x815: (0x35B, "front", (0.25, 0.48, 0.75, 1.0)),        # Tooty
    0x816: (0x451, "front", (0.36, 0.50, 0.64, 0.92)),       # Gruntilda
    0x82B: (0x46A, "front", (0.36, 0.55, 0.64, 1.0)),        # Klungo
    0x802: (0x3BB, "front", (0.30, 0.55, 0.70, 1.0)),        # Jinjos
    0x803: (0x3C2, "front", (0.30, 0.55, 0.70, 1.0)),
    0x804: (0x3C0, "front", (0.30, 0.55, 0.70, 1.0)),
    0x805: (0x3C1, "front", (0.30, 0.55, 0.70, 1.0)),
    0x806: (0x3BC, "front", (0.30, 0.55, 0.70, 1.0)),
}


def picture(model_bytes, tex, view, crop, size=32, bg=(0, 0, 0, 0)):
    return P.render3d(model_bytes, tex, size, view, crop, bg)


def frames_for(img, n):
    """Talking frames: tiny vertical bob."""
    out = []
    for k in range(n):
        if k % 2:
            b = np.zeros_like(img)
            b[1:] = img[:-1]
            out.append(b)
        else:
            out.append(img)
    return out


CLEAN_MODELS = {}      # filled by generate.gen_model: uid -> clean model bytes
_CACHE = {}


def hook(key, fact, rgba):
    if not key.startswith("s"):
        return None
    uid = int(key[1:].split(".")[0], 16)
    if uid not in PORTRAITS:
        return None
    m, view, crop = PORTRAITS[uid]
    if m not in CLEAN_MODELS:
        return None
    if uid not in _CACHE:
        d = CLEAN_MODELS[m]
        tex = {r["i"]: F.decode_region(d, r) for r in F.model_textures(d)}
        _CACHE[uid] = picture(d, tex, view, crop, max(fact["w"], fact["h"]))
    img = _CACHE[uid][:fact["h"], :fact["w"]]
    f = int(key.split(".")[1])
    return frames_for(img, f + 1)[f]
