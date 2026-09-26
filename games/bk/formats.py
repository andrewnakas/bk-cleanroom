"""BK asset formats: locate every pixel and palette region inside models and sprites.

Used by the dirty-room spec step (to take coarse facts) and by the clean generator (to overwrite
those regions with generated pixels of the same format and size). Everything outside the
regions (headers, geometry, display lists, vertices, collision) is kept as-is.

Model texture list (at header.texture_list_offset): s32 size (from the list start), s16 count, u16 pad, count x
16-byte infos {s32 offset, s16 type, u8 pad[2], u8 w, u8 h, pad[6]}, then the data. type bits:
1 CI4, 2 CI8, 4 RGBA16, 8 RGBA32 (upper bits: flags). CI textures start with their palette
(0x20 / 0x200 bytes). A texture's region runs to the next texture (mipmaps included).

Sprite: u16 frameCnt, u16 format (1 CI4, 4 CI8, 0x20 I4, 0x40 I8, 0x400 RGBA16, 0x800 RGBA32),
... 0x10 bytes header, frameCnt u32 offsets (from 0x10 + 4*frameCnt), frames of 0x14-byte header
{x, y, w, h, chunkCnt, ...}; CI: palette at the next 8-aligned offset; chunks {x, y, w, h}
+ 8-aligned pixel data. frameCnt > 0x100: one RGBA16 chunk at offset 8.
"""
import struct

from cleanroom.gfx import texfmt as T

MODEL_TYPES = {1: (T.CI, T.B4), 2: (T.CI, T.B8), 4: (T.RGBA, T.B16), 8: (T.RGBA, T.B32)}
SPRITE_TYPES = {0x1: (T.CI, T.B4), 0x4: (T.CI, T.B8), 0x20: (T.I, T.B4), 0x40: (T.I, T.B8),
                0x400: (T.RGBA, T.B16), 0x800: (T.RGBA, T.B32), 0x100: (T.IA, T.B8), 0x80: (T.IA, T.B4)}
BITS = {T.B4: 4, T.B8: 8, T.B16: 16, T.B32: 32}


def _u16(b, o):
    return struct.unpack(">H", b[o:o + 2])[0]


def _s16(b, o):
    return struct.unpack(">h", b[o:o + 2])[0]


def _u32(b, o):
    return struct.unpack(">I", b[o:o + 4])[0]


def model_textures(d):
    """-> list of regions {i, fmt, siz, w, h, pal (off,len)|None, pix (off,len), mips}"""
    if len(d) < 0x38 or _u32(d, 0) != 0xB:
        return []
    tl = _s16(d, 8)
    if tl <= 0:
        return []
    size, cnt = _u32(d, tl), _s16(d, tl + 4)
    base = tl + 8 + 16 * cnt
    infos = []
    for i in range(cnt):
        o = tl + 8 + 16 * i
        infos.append((_u32(d, o), _u16(d, o + 4), d[o + 8], d[o + 9]))
    out = []
    offs = sorted(set(x[0] for x in infos)) + [size - 8 - 16 * cnt]   # size counts from the list header
    for i, (off, typ, w, h) in enumerate(infos):
        fs = MODEL_TYPES.get(typ & 0xF)
        if fs is None or w == 0 or h == 0:
            continue
        end = min(x for x in offs if x > off)
        fmt, siz = fs
        pal = None
        p = base + off
        if fmt == T.CI:
            n = 0x20 if siz == T.B4 else 0x200
            pal = (p, n)
            p += n
        plen = w * h * BITS[siz] // 8
        total = base + end - p
        out.append({"i": i, "fmt": fmt, "siz": siz, "w": w, "h": h, "pal": pal, "pix": (p, plen),
                    "region": (p, total), "type": typ})
    return out


def sprite_chunks(d):
    """-> list of regions {frame, chunk, fmt, siz, x, y, w, h, fw, fh, pal, pix}"""
    if len(d) < 0x10:
        return []
    fcnt, form = _u16(d, 0), _u16(d, 2)
    fs = SPRITE_TYPES.get(form)
    if fs is None:
        return []
    fmt, siz = fs
    out = []
    if fcnt > 0x100:
        w, h = _u16(d, 12), _u16(d, 14)
        out.append({"frame": 0, "chunk": 0, "fmt": T.RGBA, "siz": T.B16, "x": 0, "y": 0, "w": w, "h": h,
                    "fw": w, "fh": h, "pal": None, "pix": (16, w * h * 2)})
        return out
    for f in range(fcnt):
        fo = 0x10 + 4 * fcnt + _u32(d, 0x10 + 4 * f)
        if fo + 0x14 > len(d):
            break
        fw, fh, cc = _u16(d, fo + 4), _u16(d, fo + 6), _u16(d, fo + 8)
        o = fo + 0x14
        pal = None
        if fmt == T.CI:
            o = (o + 7) & ~7
            n = 0x20 if siz == T.B4 else 0x200
            pal = (o, n)
            o += n
        for c in range(cc):
            x, y, w, h = _s16(d, o), _s16(d, o + 2), _u16(d, o + 4), _u16(d, o + 6)
            o = (o + 8 + 7) & ~7
            n = w * h * BITS[siz] // 8
            if o + n > len(d):
                break
            out.append({"frame": f, "chunk": c, "fmt": fmt, "siz": siz, "x": x, "y": y, "w": w, "h": h,
                        "fw": fw, "fh": fh, "pal": pal, "pix": (o, n)})
            o += n
    return out


def decode_region(d, r):
    """RGBA8 (h, w, 4) of a region (palette applied)."""
    import numpy as np
    pal = None
    if r["pal"]:
        po, pn = r["pal"]
        pal = T.decode(d[po:po + pn], pn // 2, 1, T.RGBA, T.B16)[0]
    return T.decode(bytes(d[r["pix"][0]:r["pix"][0] + r["pix"][1]]), r["w"], r["h"], r["fmt"], r["siz"], pal)
