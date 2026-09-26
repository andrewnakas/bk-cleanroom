"""DIRTY-ROOM CHECK: clean build vs retail, over the regenerated data.

    python -m games.bk.taint_report <v1.1 rom.z64> <dirty tree> <clean assets.bin> <clean tree>
Retail expressive streams: every model texture/palette region and sprite chunk/palette (decoded
to RGBA, and raw), and the decoded PCM of both soundfont tbls. Clean streams: the same regions of
the clean assets (v1.0 numbering, mapped back) and the clean tbls. Any shared run of >= 32 bytes
(cleanroom.taint.FAIL_RUN) fails. Kept facts (geometry, animation, text, sequences) are not scanned.
"""
import json
import os
import sys

import numpy as np

from cleanroom import taint
from cleanroom.audio import vadpcm
from games.bk import assetfs as A, audio, formats as F
from games.bk.dirty_rom import assets_bin


def regions(es):
    for e in es:
        if e.data is None:
            continue
        if e.kind == "model":
            for r in F.model_textures(e.data):
                a, n = r["region"]
                yield f"m{e.uid:x}.{r['i']}", e.data[a:a + n]
                if r["pal"]:
                    a, n = r["pal"]
                    yield f"m{e.uid:x}.{r['i']}.pal", e.data[a:a + n]
                yield f"m{e.uid:x}.{r['i']}.rgba", F.decode_region(e.data, r).tobytes()
        elif e.kind == "sprite":
            for r in F.sprite_chunks(e.data):
                a, n = r["pix"]
                k = f"s{e.uid:x}.{r['frame']}.{r['chunk']}"
                yield k, e.data[a:a + n]
                if r["pal"] and r["chunk"] == 0:
                    a, n = r["pal"]
                    yield k + ".pal", e.data[a:a + n]
                yield k + ".rgba", F.decode_region(e.data, r).tobytes()


def pcm_streams(ctl, tbl):
    for base, ws in audio.waves(ctl).items():
        w = ws[0]
        if w["book"] and any(w["book"]["book"]):
            yield f"wave@{base:x}", vadpcm.decode(tbl[base:base + w["len"]], w["book"], w["len"] // 9 * 16).astype("<i2").tobytes()
        yield f"adpcm@{base:x}", tbl[base:base + w["len"]]


def main(argv):
    rom, dirty, clean_assets, clean = argv[1:5]
    ret = A.parse(assets_bin(open(rom, "rb").read()))
    cl = [e for e in A.parse(open(clean_assets, "rb").read())]
    raw = lambda es: ((k, s) for k, s in regions(es) if not k.endswith(".rgba"))
    rgba = lambda es: ((k, s) for k, s in regions(es) if k.endswith(".rgba"))
    hits = taint.scan(taint.build_index(s for _, s in raw(ret)), raw(cl))
    hits += taint.scan(taint.build_index((s for _, s in rgba(ret)), unit=4), rgba(cl), unit=4)
    streams = []
    for n in (1, 2) if "--no-audio" not in argv else ():
        streams += list(pcm_streams(open(f"{dirty}/bin/soundfont{n}ctl.bin", "rb").read(),
                                    open(f"{dirty}/bin/soundfont{n}tbl.bin", "rb").read()))
    aidx = taint.build_index(s for _, s in streams)
    ahits = []
    for n in (1, 2) if "--no-audio" not in argv else ():
        ahits += taint.scan(aidx, pcm_streams(open(f"{clean}/bin/soundfont{n}ctl.bin", "rb").read(),
                                              open(f"{clean}/bin/soundfont{n}tbl.bin", "rb").read()))
    fail = [h for h in hits + ahits if h[3] >= taint.FAIL_RUN]
    print(f"taint: textures {sum(1 for _ in regions(cl))} streams, {len(hits)} with any shared window; "
          f"audio {len(ahits)}; FAILING (>= {taint.FAIL_RUN} B run): {len(fail)}")
    for h in sorted(fail, key=lambda h: -h[3])[:8]:
        print("  ", h)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
