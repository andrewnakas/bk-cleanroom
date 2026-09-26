"""Picture <-> texture projection through a model's own triangles.

render(model_bytes, tex_rgba, scale) -> (canvas RGBA, bbox): orthographic XY render of the textured
    triangles (dev check / illustration renders).
bake(model_bytes, canvas_fn) -> {texture index: RGBA}: for every texel of every texture used by a
    triangle, find its model-space XY (barycentric through the triangle's UVs) and sample
    canvas_fn(x, y arrays) -> RGBA. Texels no triangle covers get the nearest covered colour.
"""
import numpy as np

from games.bk import formats as F, modelgeo as G


def _bary(p, a, b, c):
    v0, v1 = b - a, c - a
    v2 = p - a[None]
    d00, d01, d11 = (v0 * v0).sum(), (v0 * v1).sum(), (v1 * v1).sum()
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-9:
        return None
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return 1 - v - w, v, w


def bake(d, canvas_fn, only=None):
    tb = G.tris_by_texture(d)
    out = {}
    for r in F.model_textures(d):
        i = r["i"]
        if i not in tb or (only is not None and i not in only):
            continue
        w, h = r["w"], r["h"]
        ys, xs = np.mgrid[0:h, 0:w]
        uv = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1).astype(np.float64)
        xy = np.full((w * h, 2), np.nan)
        for pos, st in tb[i]:
            s = np.array(st, np.float64)
            # wrap UVs into the texture (tiles often use s in [0, w] plus an offset)
            s0 = np.floor(s.mean(0) / [w, h]) * [w, h]
            s = s - s0
            a, b_, c = s
            bc = _bary(uv, a, b_, c)
            if bc is None:
                continue
            l0, l1, l2 = bc
            inside = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02) & np.isnan(xy[:, 0])
            P = np.array(pos, np.float64)[:, :2]
            xy[inside] = (l0[inside, None] * P[0] + l1[inside, None] * P[1] + l2[inside, None] * P[2])
        ok = ~np.isnan(xy[:, 0])
        if not ok.any():
            continue
        if not ok.all():                        # nearest covered texel
            idx = np.nonzero(ok)[0]
            miss = np.nonzero(~ok)[0]
            dd = ((uv[miss, None, :] - uv[None, idx, :]) ** 2).sum(-1)
            xy[miss] = xy[idx[dd.argmin(1)]]
        out[i] = np.asarray(canvas_fn(xy[:, 0], xy[:, 1]), np.uint8).reshape(h, w, 4)
    return out


def render(d, tex, scale=1.0, bg=(0, 0, 0, 0)):
    """tex: {index: RGBA}. Nearest-texel orthographic render (x right, y up)."""
    tb = G.tris_by_texture(d)
    pts = np.array([p[:2] for t in tb.values() for tri in t for p in tri[0]], np.float64)
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    W, H = int((x1 - x0) * scale) + 1, int((y1 - y0) * scale) + 1
    img = np.zeros((H, W, 4), np.uint8)
    img[:] = bg
    gy, gx = np.mgrid[0:H, 0:W]
    P = np.stack([x0 + (gx.ravel() + 0.5) / scale, y1 - (gy.ravel() + 0.5) / scale], 1)
    for i, tris in tb.items():
        if i not in tex:
            continue
        t = tex[i]
        th, tw = t.shape[:2]
        for pos, st in tris:
            q = np.array(pos, np.float64)[:, :2]
            bc = _bary(P, q[0], q[1], q[2])
            if bc is None:
                continue
            l0, l1, l2 = bc
            m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not m.any():
                continue
            s = np.array(st, np.float64)
            u = l0[m] * s[0, 0] + l1[m] * s[1, 0] + l2[m] * s[2, 0]
            v = l0[m] * s[0, 1] + l1[m] * s[1, 1] + l2[m] * s[2, 1]
            px = t[np.mod(v.astype(int), th), np.mod(u.astype(int), tw)]
            flat = img.reshape(-1, 4)
            sel = np.nonzero(m)[0]
            keep = px[:, 3] > 0
            flat[sel[keep]] = px[keep]
    return img, (x0, y0, x1, y1)
