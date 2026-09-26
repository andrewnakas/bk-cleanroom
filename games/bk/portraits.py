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

HEAD = (0.28, 0.52, 0.72, 1.0)
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


# the rest: v1.1 sprite -> model, framing ('head' or 'whole'); matched by name (portrait_auto)
_H, _W = "head", "whole"
MORE = {0x7F1: (0x370, _H), 0x7F2: (0x35C, _H), 0x7F3: (0x3CB, _W), 0x7F5: (0x35D, _H), 0x7F6: (0x385, _W),
        0x7F7: (0x3E0, _H), 0x7F9: (0x3F8, _H), 0x7FA: (0x4DF, _W), 0x7FB: (0x3DD, _H), 0x7FD: (0x3D5, _W),
        0x7FF: (0x371, _W), 0x800: (0x38F, _W), 0x801: (0x3DF, _H), 0x809: (0x485, _W), 0x80C: (0x366, _W),
        0x80D: (0x35F, _W), 0x80F: (0x3C7, _W), 0x810: (0x363, _W), 0x812: (0x361, _W), 0x817: (0x3E8, _H),
        0x81E: (0x547, _W), 0x81F: (0x549, _W), 0x820: (0x548, _W), 0x821: (0x448, _W), 0x822: (0x47F, _W),
        0x823: (0x480, _W), 0x824: (0x481, _W), 0x825: (0x2D2, _W), 0x827: (0x46F, _W), 0x828: (0x2E6, _W),
        0x82A: (0x51A, _W), 0x82C: (0x4C7, _H), 0x82E: (0x539, _H), 0x82F: (0x3F8, _H), 0x830: (0x422, _W),
        0x833: (0x450, _W), 0x834: (0x350, _W), 0x835: (0x494, _H), 0x836: (0x372, _W), 0x837: (0x48F, _W),
        0x838: (0x41C, _W), 0x83A: (0x425, _W), 0x83B: (0x88C, _W), 0x83C: (0x38A, _H), 0x83D: (0x519, _W),
        0x841: (0x468, _H), 0x843: (0x44C, _W), 0x844: (0x469, _H), 0x845: (0x566, _W), 0x847: (0x428, _W),
        0x849: (0x3D4, _W)}
# renders that come out wrong (bad name matches): these keep the default colour-grid pictures
DROP = {0x7F6, 0x7F7, 0x828, 0x83B}
for _s, (_m, _f) in MORE.items():
    if _s in DROP:
        continue
    PORTRAITS.setdefault(_s, (_m, "front", HEAD if _f == _H else WHOLE))


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
