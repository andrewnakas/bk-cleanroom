"""BK model geometry: which triangles (positions + texture coordinates) use each texture.

Model file: header (see formats.py), display list at gfx_list_offset (u32 count, u32 pad, then
F3DEX commands), vertex list at vtx_list_offset (0x18-byte header, then 16-byte Vtx).
Segments: 1 = vertices, 2 = texture data, 3 = this display list. F3DEX: G_VTX 0x04
(v0*2 in bits 16..23, n in bits 10..15), G_TRI1 0xBF, G_TRI2 0xB1, G_DL 0x06, G_ENDDL 0xB8,
G_SETTIMG 0xFD, G_SETTILESIZE 0xF2 (for the texture's size in UV units).

    tris_by_texture(model_bytes) -> {texture index: [((x,y,z)*3, (s,t)*3), ...]}
s,t are in texels (the Vtx's 10.5 fixed point / 32, times the G_TEXTURE scale).
"""
import struct

from games.bk import formats as F


def _vtx(d, base, i):
    x, y, z, fl, s, t = struct.unpack_from(">hhhHhh", d, base + 16 * i)
    return (x, y, z), (s / 32.0, t / 32.0)


def tris_by_texture(d):
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
        offs.setdefault(struct.unpack_from(">I", d, o)[0], i)
    vbase = vtx + 0x18
    gbase = gfx + 8
    ncmd = struct.unpack_from(">I", d, gfx)[0]
    out = {}
    cache = [None] * 64
    cur = [None]
    scale = [1.0, 1.0]

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
                        cache[v0 + k] = (p, (s_ * scale[0], t_ * scale[1]))
            elif op in (0xBF, 0xB1):
                ids = [((w1 >> 16) & 0xFF) // 2, ((w1 >> 8) & 0xFF) // 2, (w1 & 0xFF) // 2] if op == 0xBF else \
                    [((w0 >> 16) & 0xFF) // 2, ((w0 >> 8) & 0xFF) // 2, (w0 & 0xFF) // 2,
                     ((w1 >> 16) & 0xFF) // 2, ((w1 >> 8) & 0xFF) // 2, (w1 & 0xFF) // 2]
                if cur[0] is not None:
                    for j in range(0, len(ids), 3):
                        vs = [cache[i] for i in ids[j:j + 3]]
                        if all(vs):
                            out.setdefault(cur[0], []).append(([v[0] for v in vs], [v[1] for v in vs]))
            elif op == 0xBB:                      # G_TEXTURE: s/t scale (0xFFFF ~ 1.0)
                scale[0] = max(1, w1 >> 16) / 65536.0
                scale[1] = max(1, w1 & 0xFFFF) / 65536.0
            elif op == 0xFD:
                seg, off = w1 >> 24, w1 & 0xFFFFFF
                cur[0] = offs.get(off) if seg == 2 else None
            elif op == 0x06:
                if (w1 >> 24) == 3 and depth < 8:
                    run(w1 & 0xFFFFFF, depth + 1)
                if (w0 >> 16) & 0xFF == 1:        # branch (no return)
                    return
            elif op == 0xB8:
                return

    run(0)
    return out
