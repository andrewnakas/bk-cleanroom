"""BK asset filesystem (assets.bin): parse and rebuild. Replaces bk_asset_tool (its rarezip
C library does not build on Windows).

Layout: u32 slot count, u32 0xFFFFFFFF, then count x (u32 offset, u8 0, u8 compressed, u16 flags),
then data. The last slot is a terminator (flags 4) whose offset is the data size.
Compressed assets: 0x11 0x72, u32 BE size, raw deflate (Rare's gzip 1.2.4), padded with 0xAA to 8 bytes.
Segment of each asset (bk_asset_tool's classification):
  0 animation, 1/3 model or sprite, 2 level setup, 4 dialog/quiz/demo, 5 model, 6 midi, else binary
"""
import struct
import zlib

PAD = 8


def unzip(b):
    assert b[:2] == b"\x11\x72", "no bk header"
    size = struct.unpack(">I", b[2:6])[0]
    out = zlib.decompressobj(-15).decompress(b[6:], size)
    assert len(out) == size
    return out


_RZ = None


def _rarezip():
    """Rare's compressor (gzip 1.2.4 deflate, from the decomp's rarezip tool) built as a DLL:
    the game's inflate uses a fixed-size Huffman table buffer, and zlib's streams overflow it."""
    global _RZ
    if _RZ is None:
        import ctypes
        import os
        _RZ = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "..", "tools", "rarezip", "rarezip.dll"))
        _RZ.bk_zip.restype = ctypes.c_size_t
        _RZ.bk_zip.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
    return _RZ


def zip_(b, pad=True):
    import ctypes
    b = bytes(b)
    cap = len(b) + len(b) // 8 + 0x1000
    out = ctypes.create_string_buffer(cap)
    n = _rarezip().bk_zip(b, len(b), out, cap)
    out = out.raw[:n]
    return out + bytes([0xAA]) * (-len(out) % PAD) if pad else out


class Entry:
    __slots__ = ("uid", "seg", "compressed", "flags", "data", "raw")

    def __init__(self, uid, seg, compressed, flags, data, raw=None):
        self.uid, self.seg, self.compressed, self.flags, self.data, self.raw = uid, seg, compressed, flags, data, raw

    @property
    def kind(self):
        d, s = self.data, self.seg
        if d is None:
            return "empty"
        if s == 0:
            return "anim"
        if s in (1, 3):
            return "model" if d[:4] == b"\0\0\0\x0b" else "sprite"
        if s == 2:
            return "setup"
        if s == 4:
            if d[:5] == b"\x01\x01\x02\x05\x00":
                return "quiz"
            if d[:5] == b"\x01\x03\x00\x05\x00":
                return "grunty_q"
            if d[:3] == b"\x01\x03\x00":
                return "dialog"
            return "demo"
        if s == 5:
            return "model"
        if s == 6:
            return "midi"
        return "bin"


def parse(buf):
    n = struct.unpack(">I", buf[:4])[0]
    meta = [struct.unpack(">IBBH", buf[8 + 8 * i:16 + 8 * i]) for i in range(n)]
    base = 8 + 8 * n
    out, seg, prev_t = [], 0, 3
    for i in range(n - 1):
        off, _, c, t = meta[i]
        if t == 4:
            out.append(Entry(i, 0, bool(c), t, None))
            continue
        if t != 2 and (prev_t & 2) != (t & 2):
            seg += 1
            prev_t = t
        raw = buf[base + off:base + meta[i + 1][0]]
        data = unzip(raw) if c else raw
        out.append(Entry(i, seg, bool(c), t, data, raw))
    return out


def build(entries, keep_raw=False):
    """entries: list from parse (possibly with .data replaced). keep_raw reuses the original
    compressed bytes when data is unchanged (dev round-trip only)."""
    blobs = []
    for e in entries:
        if e.data is None:
            blobs.append(b"")
        elif keep_raw and e.raw is not None:
            blobs.append(e.raw)
        elif e.compressed:
            blobs.append(zip_(e.data))
        else:
            d = bytes(e.data)
            blobs.append(d + b"\0" * (-len(d) % 8))
    n = len(entries) + 1
    head = struct.pack(">II", n, 0xFFFFFFFF)
    table, off = [], 0
    for e, b in zip(entries, blobs):
        table.append(struct.pack(">IBBH", off, 0, int(e.compressed), e.flags))
        off += len(b)
    table.append(struct.pack(">IBBH", off, 0, 0, 4))
    out = head + b"".join(table) + b"".join(blobs)
    return out + b"\0" * (-len(out) % 16)


if __name__ == "__main__":
    import collections
    import sys
    buf = open(sys.argv[1], "rb").read()
    es = parse(buf)
    print(len(es), "slots;", collections.Counter(e.kind for e in es))
    print("compressed", sum(e.compressed for e in es if e.data is not None),
          "raw mod16", collections.Counter(len(e.raw) % 16 for e in es if e.raw))
    rb = build(es, keep_raw=True)
    print("keep_raw rebuild identical:", rb[:len(buf)] == buf[:len(rb)], len(rb), len(buf))
