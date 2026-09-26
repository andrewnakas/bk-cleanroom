"""BK model geometry: which triangles (positions + texture coordinates) use each texture.

Model file: header (see formats.py), display list at gfx_list_offset (u32 count, u32 pad, then
F3DEX commands), vertex list at vtx_list_offset (0x18-byte header, then 16-byte Vtx).
Segments: 1 = vertices, 2 = texture data, 3 = this display list. F3DEX: G_VTX 0x04
(v0*2 in bits 16..23, n in bits 10..15), G_TRI1 0xBF, G_TRI2 0xB1, G_DL 0x06, G_ENDDL 0xB8,
G_SETTIMG 0xFD, G_SETTILESIZE 0xF2 (for the texture's size in UV units).

    tris_by_texture(model_bytes, all_tris=None) -> {texture index: [((x,y,z)*3, (s,t)*3), ...]}
        all_tris (a list) also receives every triangle: (pos*3, st*3, rgba*3, texture index or None, lit)
        lit: G_LIGHTING was on, so the rgba bytes are a signed normal
s,t are in texels (the Vtx's 10.5 fixed point / 32, times the G_TEXTURE scale).
"""
import struct

from games.bk import formats as F


def _vtx(d, base, i):
    x, y, z, fl, s, t = struct.unpack_from(">hhhHhh", d, base + 16 * i)
    return (x, y, z), (s / 32.0, t / 32.0)


def _vcol(d, base, i):
    return tuple(d[base + 16 * i + 12:base + 16 * i + 16])


def tris_by_texture(d, all_tris=None):
    if len(d) < 0x38 or struct.unpack_from(">I", d, 0)[0] != 0xB:
        return {}
    gfx = struct.unpack_from(">i", d, 0xC)[0]
    vtx = struct.unpack_from(">i", d, 0x10)[0]
    if gfx <= 0 or vtx <= 0:
        return {}
    texs = F.model_textures(d)
    tl = struct.unpack_from(">h", d, 8)[0]
    cnt = struct.unpack_from(">h", d, tl + 4)[0] if tl > 0 else 0
    offs = {}
    for i in range(cnt):
        o = tl + 8 + 16 * i
        off, typ = struct.unpack_from(">IH", d, o)
        offs.setdefault(off, i)
        if typ & 1:
            offs.setdefault(off + 0x20, i)      # CI4: pixels follow the 16-colour palette
        if typ & 2:
            offs.setdefault(off + 0x200, i)     # CI8
    vbase = vtx + 0x18
    gbase = gfx + 8
    ncmd = struct.unpack_from(">I", d, gfx)[0]
    out = {}
    cache = [None] * 64
    cur = [None]
    scale = [1.0, 1.0]
    textured = [True]
    lit = [False]      # the game enables texturing before drawing; only an explicit G_TEXTURE off disables it

    def run(pc, depth=0):
        while 0 <= pc < ncmd * 8 and gbase + pc + 8 <= len(d):
            w0, w1 = struct.unpack_from(">II", d, gbase + pc)
            op = w0 >> 24
            pc += 8
            if op == 0x04:
                v0 = ((w0 >> 16) & 0xFF) // 2
                n = (w0 >> 10) & 0x3F
                a = (w1 & 0xFFFFFF) // 16
                for k in range(n):
                    if v0 + k < 64 and vbase + 16 * (a + k) + 16 <= len(d):
                        p, (s_, t_) = _vtx(d, vbase, a + k)
                        cache[v0 + k] = (p, (s_ * scale[0], t_ * scale[1]), _vcol(d, vbase, a + k))
            elif op in (0xBF, 0xB1):
                ids = [((w1 >> 16) & 0xFF) // 2, ((w1 >> 8) & 0xFF) // 2, (w1 & 0xFF) // 2] if op == 0xBF else \
                    [((w0 >> 16) & 0xFF) // 2, ((w0 >> 8) & 0xFF) // 2, (w0 & 0xFF) // 2,
                     ((w1 >> 16) & 0xFF) // 2, ((w1 >> 8) & 0xFF) // 2, (w1 & 0xFF) // 2]
                if True:
                    for j in range(0, len(ids), 3):
                        vs = [cache[i] for i in ids[j:j + 3]]
                        if all(vs):
                            if cur[0] is not None:
                                out.setdefault(cur[0], []).append(([v[0] for v in vs], [v[1] for v in vs]))
                            if all_tris is not None:
                                all_tris.append(([v[0] for v in vs], [v[1] for v in vs], [v[2] for v in vs],
                                                 cur[0] if textured[0] else None, lit[0]))
            elif op == 0xB7 and w1 & 0x20000:     # G_SETGEOMETRYMODE: G_LIGHTING (vertex rgba = normals)
                lit[0] = True
            elif op == 0xB6 and w1 & 0x20000:
                lit[0] = False
            elif op == 0xBB:                      # G_TEXTURE: s/t scale (0xFFFF ~ 1.0), on/off
                scale[0] = max(1, w1 >> 16) / 65536.0
                scale[1] = max(1, w1 & 0xFFFF) / 65536.0
                textured[0] = bool(w0 & 0xFF)
            elif op == 0xFD:
                seg, off = w1 >> 24, w1 & 0xFFFFFF
                cur[0] = offs.get(off) if seg == 2 else None
            elif op == 0x06:
                if (w0 >> 16) & 0xFF == 1:        # branch (no return)
                    return
            elif op == 0xB8:
                return

    # the display list is a set of chunks called from the model's geo list: walk them all in order
    run_all(run, ncmd, gbase, d)
    return out


def run_all(run, ncmd, gbase, d):
    pc = 0
    while pc < ncmd * 8:
        run(pc)
        # continue after the next ENDDL
        while pc < ncmd * 8 and struct.unpack_from(">I", d, gbase + pc)[0] >> 24 != 0xB8:
            pc += 8
        pc += 8
