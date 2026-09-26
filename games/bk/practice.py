"""Practice pack for recording BK's character voices (PERSONAL USE: made from your own ROM's dirty
tree, written outside the repo, never published).

    python -m games.bk.practice <dirty tree> <out dir>
Writes clips/<id>_<NAME>.wav (the reference sound to imitate), <CHARACTER>.wav call-and-response
tracks (clip, beep, a gap to repeat it) and SCRIPT.txt. To use your own takes: save each as
games/bk/voices/<id>.wav (mono, any length; it is fitted to the slot) and rebuild the audio
(make_clean without --skip-audio). takes are your own performances, so they can be published.
"""
import os
import sys
import wave

import numpy as np

from cleanroom.audio import vadpcm
from games.bk import audio, voices

HZ = 22050


def wr(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(HZ)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main(argv):
    dirty, out = argv[1], argv[2]
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)
    ctl = open(os.path.join(dirty, "bin/soundfont1ctl.bin"), "rb").read()
    tbl = open(os.path.join(dirty, "bin/soundfont1tbl.bin"), "rb").read()
    from cleanroom.audio import albank
    sounds = albank.parse_bankfile(ctl)["banks"][0]["insts"][0]["sounds"]
    by_who = {}
    lines = []
    for i, v in sorted(voices.voice_slots().items()):
        if i >= len(sounds):
            continue
        w = sounds[i]["wave"]
        x = vadpcm.decode(tbl[w["base"]:w["base"] + w["len"]], w["book"], w["len"] // 9 * 16).astype(np.float32) / 32768
        wr(os.path.join(out, "clips", f"{i}_{v['name']}.wav"), x)
        by_who.setdefault(v["who"], []).append((i, v, x))
        lines.append(f"{i:4d}  {v['who']:10s} {v['name']:32s} say: {v['text']}")
    beep = 0.3 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * HZ)) / HZ).astype(np.float32)
    for who, items in by_who.items():
        parts = []
        for i, v, x in items:
            gap = np.zeros(int((1.5 * len(x) / HZ + 1.5) * HZ), np.float32)
            parts += [x, np.zeros(int(0.3 * HZ), np.float32), beep, gap]
        wr(os.path.join(out, f"{who}.wav"), np.concatenate(parts))
    open(os.path.join(out, "SCRIPT.txt"), "w").write(
        "BK voice practice pack (personal use; never publish these clips)\n"
        "Record each line and save it as games/bk/voices/<id>.wav, then rebuild audio.\n\n" + "\n".join(lines) + "\n")
    print(f"practice: {len(lines)} lines, {len(by_who)} character tracks -> {out}")


if __name__ == "__main__":
    main(sys.argv)
