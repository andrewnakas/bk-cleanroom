"""Placeholder character voices (Piper TTS, our own performances) for BK's voice sound effects.

BK's voices are short vocal sound effects in soundfont 1 (one instrument; sound index = SFX id,
named in the decomp's enum: SFX_31_BANJO_OHHWAAOOO, SFX_B4_BOTTLES_TALKING_1, ...). For every SFX
whose name belongs to a character, we speak the name's syllables (or gibberish for *_TALKING) in a
character voice, lift the pitch, and fit the slot's length. The user can replace any line with
their own recording later (voices/<id>.wav is simply overwritten; see practice pack).

    python -m games.bk.voices build [--only BANJO]    -> games/bk/voices/<sfx id>.wav + voices.json
audio.build(..., overrides=voices.override) uses them.
"""
import json
import os
import re
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "voices")
PIPER = os.environ.get("PIPER_VOICES", "C:/Users/andre/n64work/piper_voices")
ENUMS = os.environ.get("BK_ENUMS", "D:/n64work/bk/pristine/include/enums.h")

# character -> (piper model, semitones up, speaking length scale)
CAST = {"BANJO": ("en_US-ryan-high", 2, 1.0), "KAZOOIE": ("en_US-amy-medium", 8, 0.9),
        "MUMBO": ("en_US-joe-medium", 1, 1.1), "BOTTLES": ("en_US-joe-medium", 6, 0.9),
        "GRUNTY": ("en_US-kristin-medium", 3, 1.0), "GRUNTILDA": ("en_US-kristin-medium", 3, 1.0),
        "TOOTY": ("en_US-amy-medium", 6, 0.9), "JINJO": ("en_US-amy-medium", 11, 0.8),
        "BRENTILDA": ("en_US-hfc_female-medium", 2, 1.0), "KLUNGO": ("en_US-joe-medium", -2, 1.1),
        "CHEATO": ("en_US-ryan-high", 5, 0.9), "VILE": ("en_US-joe-medium", 2, 1.0)}
GIBBERISH = ["guh huh", "ah hah", "buh duh", "ooh ah", "heh huh", "oh eh", "wuh huh", "ha huh"]


def sfx_names():
    out = {}
    for l in open(ENUMS, encoding="latin1"):
        m = re.match(r"\s*SFX_([0-9A-F]+)_(\w+)", l)
        if m:
            out[int(m.group(1), 16)] = m.group(2)
    return out


def voice_slots():
    out = {}
    for i, n in sfx_names().items():
        who = next((c for c in CAST if n.startswith(c + "_")), None)
        if who is None or any(k in n for k in ("LANDING", "SKIDDING", "FOOTSTEP", "DROWNING")):
            continue
        words = n[len(who) + 1:]
        if "TALKING" in words:
            text = GIBBERISH[i % len(GIBBERISH)]
        else:
            words = re.sub(r"_?\d+$", "", words).replace("_", " ").lower()
            text = re.sub(r"(.)\1{2,}", r"\1\1", words)      # "ruuuuuh" -> "ruuh"
        out[i] = {"who": who, "name": n, "text": text}
    return out


_V = {}


def speak(who, text, n, rate):
    import librosa
    from piper import PiperVoice, SynthesisConfig
    model, semi, length = CAST[who]
    if model not in _V:
        _V[model] = PiperVoice.load(os.path.join(PIPER, model + ".onnx"))
    v = _V[model]
    f = 2 ** (semi / 12)
    cfg = SynthesisConfig(length_scale=length * f, noise_scale=0.8, noise_w_scale=0.9)
    x = np.concatenate([c.audio_float_array for c in v.synthesize(text + "!", syn_config=cfg)]).astype(np.float32)
    x = librosa.resample(x, orig_sr=v.config.sample_rate * f, target_sr=rate).astype(np.float32)
    nz = np.nonzero(np.abs(x) > 0.01)[0]
    if len(nz):
        x = x[max(0, nz[0] - 200):nz[-1] + 400]
    if len(x) > n:                                    # speed up to fit the slot
        x = librosa.effects.time_stretch(x, rate=len(x) / n * 1.02)[:n]
    x = np.pad(x, (0, n - len(x)))
    fade = min(256, n // 8)
    if fade:
        x[-fade:] *= np.linspace(1, 0, fade)
    return x / max(1e-3, np.abs(x).max()) * 0.8


def build(spec_dir, only=None):
    S = json.load(open(os.path.join(spec_dir, "sound/samples1.json")))
    ctl = open(os.path.join(spec_dir, "sound/soundfont1ctl.bin"), "rb").read()
    from cleanroom.audio import albank
    bf = albank.parse_bankfile(ctl)
    sounds = bf["banks"][0]["insts"][0]["sounds"]
    os.makedirs(OUT, exist_ok=True)
    slots = voice_slots()
    made = {}
    for i, v in slots.items():
        if only and v["who"] != only or i >= len(sounds):
            continue
        base = sounds[i]["wave"]["base"]
        d = S["waves"].get(str(base))
        if not d:
            continue
        x = speak(v["who"], v["text"], d["nframes"], d["rate"])
        with wave.open(os.path.join(OUT, f"{i}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(d["rate"])
            w.writeframes((x * 32767).astype("<i2").tobytes())
        made[i] = dict(v, base=base, frames=d["nframes"])
    json.dump(made, open(os.path.join(OUT, "voices.json"), "w"), indent=1)
    print(f"voices: {len(made)} placeholder lines -> {OUT}")


_BY_BASE = None


def override(n, base, d):
    """audio.build hook: bank 1 waves that have a voice line."""
    global _BY_BASE
    if n != 1:
        return None
    if _BY_BASE is None:
        p = os.path.join(OUT, "voices.json")
        _BY_BASE = {v["base"]: k for k, v in json.load(open(p)).items()} if os.path.exists(p) else {}
    k = _BY_BASE.get(base)
    if k is None:
        return None
    with wave.open(os.path.join(OUT, f"{k}.wav")) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else "D:/n64work/bk/spec",
              sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None)
