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


def render3d(d, tex, size=64, view="front", crop=None, bg=(0, 0, 0, 0)):
    """Z-buffered orthographic render of all triangles (textured x vertex colour, or vertex colour).
    view: 'front' looks down -z (model faces +z). crop: (x0, y0, x1, y1) fractions of the model's
    x/y extent (y up) to frame; the output is size x size, aspect kept."""
    tris = []
    G.tris_by_texture(d, tris)
    if not tris:
        return None
    P3 = np.array([t[0] for t in tris], np.float64)          # (n, 3, 3)
    if view == "front":
        X, Y, Z = P3[..., 0], P3[..., 1], P3[..., 2]
    else:                                                      # 'back'
        X, Y, Z = -P3[..., 0], P3[..., 1], -P3[..., 2]
    x0, x1, y0, y1 = X.min(), X.max(), Y.min(), Y.max()
    if crop:
        cx0, cy0, cx1, cy1 = crop
        x0, x1 = x0 + (x1 - x0) * cx0, x0 + (x1 - x0) * cx1
        y0, y1 = y0 + (y1 - y0) * cy0, y0 + (y1 - y0) * cy1
    span = max(x1 - x0, y1 - y0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    ss = 3
    N = size * ss
    img = np.zeros((N, N, 4), np.float32)
    img[:] = bg
    zb = np.full((N, N), -1e18)
    gy, gx = np.mgrid[0:N, 0:N]
    L = np.array([-0.35, 0.55, 0.76])
    for k, (pos, st, col, ti, lit) in enumerate(tris):
        if lit:                                  # rgba holds a signed normal: simple lambert shading
            nrm = np.array([[((c[j] + 128) % 256) - 128 for j in range(3)] for c in col], np.float64)
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1)
            if view != "front":
                nrm[:, [0, 2]] *= -1
            sh = 0.5 + 0.6 * np.clip(nrm @ L, 0, 1)
            col = [(255 * v, 255 * v, 255 * v, 255) for v in sh]
        sx = (X[k] - mx) / span * N + N / 2
        sy = N / 2 - (Y[k] - my) / span * N
        bx0, bx1 = int(max(0, np.floor(sx.min()))), int(min(N - 1, np.ceil(sx.max())))
        by0, by1 = int(max(0, np.floor(sy.min()))), int(min(N - 1, np.ceil(sy.max())))
        if bx1 < bx0 or by1 < by0:
            continue
        py, px = gy[by0:by1 + 1, bx0:bx1 + 1] + 0.5, gx[by0:by1 + 1, bx0:bx1 + 1] + 0.5
        pts = np.stack([px.ravel(), py.ravel()], 1)
        bc = _bary(pts, np.array([sx[0], sy[0]]), np.array([sx[1], sy[1]]), np.array([sx[2], sy[2]]))
        if bc is None:
            continue
        l0, l1, l2 = bc
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any():
            continue
        z = l0 * Z[k][0] + l1 * Z[k][1] + l2 * Z[k][2]
        zz = zb[by0:by1 + 1, bx0:bx1 + 1].ravel()
        m &= z > zz
        if not m.any():
            continue
        c = np.array(col, np.float64)
        rgba = (l0[m, None] * c[0] + l1[m, None] * c[1] + l2[m, None] * c[2])
        if ti is not None and ti in tex:
            t = tex[ti]
            th, tw = t.shape[:2]
            s_ = np.array(st, np.float64)
            u = l0[m] * s_[0, 0] + l1[m] * s_[1, 0] + l2[m] * s_[2, 0]
            v = l0[m] * s_[0, 1] + l1[m] * s_[1, 1] + l2[m] * s_[2, 1]
            tx = t[np.mod(np.floor(v).astype(int), th), np.mod(np.floor(u).astype(int), tw)].astype(np.float64)
            keep = tx[:, 3] > 64
            rgba = np.concatenate([rgba[:, :3] * tx[:, :3] / 255.0, np.full((len(tx), 1), 255.0)], 1)
            idx = np.nonzero(m)[0][keep]
            rgba = rgba[keep]
            z = z[m][keep]
        else:
            idx = np.nonzero(m)[0]
            rgba = np.concatenate([rgba[:, :3], np.full((len(rgba), 1), 255.0)], 1)
            z = z[m]
        sub = img[by0:by1 + 1, bx0:bx1 + 1].reshape(-1, 4)
        sub[idx] = rgba
        img[by0:by1 + 1, bx0:bx1 + 1] = sub.reshape(by1 - by0 + 1, bx1 - bx0 + 1, 4)
        zsub = zb[by0:by1 + 1, bx0:bx1 + 1].reshape(-1)
        zsub[idx] = z
        zb[by0:by1 + 1, bx0:bx1 + 1] = zsub.reshape(by1 - by0 + 1, bx1 - bx0 + 1)
    return img.reshape(size, ss, size, ss, 4).mean((1, 3)).clip(0, 255).astype(np.uint8)
