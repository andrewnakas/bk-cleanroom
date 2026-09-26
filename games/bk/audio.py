"""BK soundfonts (libultra ALBankFile ctl + tbl, two banks: SFX and instruments).

Dirty room:  python -m games.bk.audio spec <dirty tree> <spec dir>
  -> spec/sound/soundfont{1,2}ctl.bin (bank structure kept: envelopes, keymaps, tuning, loop points;
     ADPCM books and loop states zeroed) and samples{1,2}.json: per wave table its tbl offset/len,
     frame count, loop, ctl offsets of book and loop, a coarse spectral outline and median pitch.
Clean room:  build(spec_dir, n) -> (ctl bytes, tbl bytes): every wave resynthesised from its outline,
  encoded with our own 4-predictor VADPCM book (same size as the bank's books), loop states from our data.
"""
import json
import os
import struct
import sys

import numpy as np

from cleanroom.audio import albank, descriptor, vadpcm
from cleanroom.audio.pitch import median_f0
from cleanroom.decomp import gen

RATE = 22050


def waves(ctl):
    bf = albank.parse_bankfile(ctl)
    out = {}
    b = bf["banks"][0]
    for inst in [b["percussion"]] + b["insts"]:
        if not inst:
            continue
        for s in inst["sounds"]:
            w = s["wave"]
            out.setdefault(w["base"], []).append(w)
    return out


def k_predictors(x, k=4):
    """Our own predictor set: k-means over per-16-sample 2nd-order LPC fits."""
    fits = []
    for s in range(2, len(x) - 16, 16):
        y, p1, p2 = x[s:s + 16], x[s - 1:s + 15], x[s - 2:s + 14]
        if (y ** 2).sum() < 1e3:
            continue
        a, *_ = np.linalg.lstsq(np.stack([p1, p2], 1), y, rcond=None)
        fits.append(a)
    base = [(1.0, 0.0), (1.8, -0.82), (0.5, 0.0), (1.4, -0.5)]
    if len(fits) < k:
        return base[:k]
    f = np.clip(np.asarray(fits), [-1.95, -0.98], [1.95, 0.98])
    c = f[np.linspace(0, len(f) - 1, k).astype(int)][np.argsort(f[np.linspace(0, len(f) - 1, k).astype(int), 0])].copy()
    for _ in range(12):
        lab = np.argmin(((f[:, None, :] - c[None]) ** 2).sum(-1), 1)
        for j in range(k):
            if (lab == j).any():
                c[j] = f[lab == j].mean(0)
    out = []
    for a1, a2 in c:
        a2 = float(np.clip(a2, -0.98, 0.98))
        out.append((float(np.clip(a1, -(1 - a2) + 0.02, (1 - a2) - 0.02)), a2))
    return out


def spec(tree, out):
    os.makedirs(os.path.join(out, "sound"), exist_ok=True)
    for n in (1, 2):
        ctl = bytearray(open(os.path.join(tree, f"bin/soundfont{n}ctl.bin"), "rb").read())
        tbl = open(os.path.join(tree, f"bin/soundfont{n}tbl.bin"), "rb").read()
        facts = {}
        books, loops = set(), set()
        for base, ws in waves(bytes(ctl)).items():
            w = ws[0]
            bo = int(w["book"]["_id"].split("@")[1], 16)
            nf = w["len"] // 9 * 16
            pcm = vadpcm.decode(tbl[base:base + w["len"]], w["book"], nf).astype(np.float64)
            d = {"len": w["len"], "nframes": nf, "rate": RATE, "desc": descriptor.describe(pcm, RATE),
                 "books": sorted({int(x["book"]["_id"].split("@")[1], 16) for x in ws}),
                 "loops": sorted({int(x["loop"]["_id"].split("@")[1], 16) for x in ws if x["loop"]})}
            if w["loop"]:
                d["loop"] = [w["loop"]["start"], w["loop"]["end"], w["loop"]["count"]]
            f0 = median_f0((pcm / 32768).astype(np.float32), RATE)
            if f0:
                d["f0"] = round(f0, 1)
            facts[base] = d
            books.update(d["books"])
            loops.update(d["loops"])
        for bo in books:                       # zero the retail books (coefficients derive from retail audio)
            order, npred = struct.unpack_from(">ii", ctl, bo)
            ctl[bo + 8:bo + 8 + 16 * order * npred] = bytes(16 * order * npred)
        for lo in loops:                       # and the ADPCM loop states
            ctl[lo + 12:lo + 44] = bytes(32)
        open(os.path.join(out, f"sound/soundfont{n}ctl.bin"), "wb").write(ctl)
        json.dump({"tbl_len": len(tbl), "waves": facts}, open(os.path.join(out, f"sound/samples{n}.json"), "w"))
        print(f"soundfont{n}: {len(facts)} waves, tbl {len(tbl)} B, {len(books)} books zeroed")


def build(spec_dir, n, overrides=None):
    ctl = bytearray(open(os.path.join(spec_dir, f"sound/soundfont{n}ctl.bin"), "rb").read())
    S = json.load(open(os.path.join(spec_dir, f"sound/samples{n}.json")))
    tbl = bytearray(S["tbl_len"])
    for key, d in S["waves"].items():
        base = int(key)
        nf = d["nframes"]
        x = None
        if overrides:
            x = overrides(n, base, d)
        if x is None:
            x = descriptor.synthesize(d["desc"], nf, d["rate"], seed=gen.h32("bk", n, base))
        x = np.pad(np.asarray(x, np.float32)[:nf], (0, max(0, nf - len(x))))
        st = en = cnt = 0
        if "loop" in d:
            st, en, cnt = d["loop"]
            if cnt and en > st + 16:
                x = descriptor.make_loop_seamless(x, st, min(en, nf))
        dither = np.random.default_rng(gen.h32("dither", n, base)).integers(-1, 2, nf)
        pcm = np.clip(np.round(np.clip(x, -1, 1) * 30000) + dither, -32768, 32767).astype(np.int16)
        order, npred = struct.unpack_from(">ii", ctl, d["books"][0])
        book = vadpcm.make_book(k_predictors(pcm.astype(np.float64), npred))
        data, _, dec = vadpcm.encode(pcm, book)
        data = bytes(data[:d["len"]]) + bytes(max(0, d["len"] - len(data)))
        tbl[base:base + d["len"]] = data
        vals = struct.pack(">%dh" % len(book["book"]), *book["book"])
        for bo in d["books"]:
            assert struct.unpack_from(">ii", ctl, bo) == (book["order"], book["npred"]), (bo, book["order"], book["npred"])
            ctl[bo + 8:bo + 8 + len(vals)] = vals
        if cnt:
            state = vadpcm.loop_state(dec, st)
            sv = struct.pack(">16h", *[int(v) for v in state])
            for lo in d["loops"]:
                ctl[lo + 12:lo + 44] = sv
    return bytes(ctl), bytes(tbl)


if __name__ == "__main__":
    if sys.argv[1] == "spec":
        spec(sys.argv[2], sys.argv[3])
