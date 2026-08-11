#!/usr/bin/env python3
"""
nova_unlock/ui/enrollment_sounds.py
Premium synthesized sounds for enrollment wizard.
No external audio files needed — all generated in memory.
"""
import math
import os
import struct
import subprocess
import tempfile
import wave

SDIR = tempfile.mkdtemp(prefix="nova_enroll_snd_")


def _wav(name, samples, rate=44100):
    path = os.path.join(SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h', max(-32767, min(32767, int(s)))))
    return path


def _silence(dur, rate=44100):
    return [0] * int(rate * dur)


def _sin(freq, dur, vol=0.4, rate=44100):
    n = int(rate * dur)
    out = []
    for i in range(n):
        t = i / rate
        env = min(1.0, min(t * 20, (dur - t) * 15))
        out.append(int(32767 * vol * env * math.sin(2 * math.pi * freq * t)))
    return out


def _exp_decay(freq, dur, vol=0.5, decay=6.0, rate=44100):
    n = int(rate * dur)
    out = []
    for i in range(n):
        t = i / rate
        env = math.exp(-t * decay) * vol
        s = math.sin(2 * math.pi * freq * t)
        s += math.sin(2 * math.pi * freq * 2 * t) * 0.3
        s += math.sin(2 * math.pi * freq * 3 * t) * 0.1
        out.append(int(32767 * env * s))
    return out


def _sweep(f0, f1, dur, vol=0.3, rate=44100):
    n = int(rate * dur)
    out = []
    for i in range(n):
        t = i / rate
        freq = f0 + (f1 - f0) * (t / dur)
        env = min(1.0, t * 15) * math.exp(-t * 2.5) * vol
        out.append(int(32767 * env * math.sin(2 * math.pi * freq * t)))
    return out


def _mix(a, b, offset=0):
    size = max(len(a), len(b) + offset)
    out = [0.0] * size
    for i, v in enumerate(a):
        out[i] += v
    for i, v in enumerate(b):
        if i + offset < size:
            out[i + offset] += v
    peak = max(abs(x) for x in out) if out else 1
    if peak > 30000:
        out = [x * 30000 / peak for x in out]
    return [int(x) for x in out]


def _make_startup():
    """
    Cinematic startup: deep whoosh → rising synth → bright chime cascade.
    Total ~1.8s. Premium, modern, confident.
    """
    rate = 44100

    # Layer 1: Deep sub whoosh (0.0s)
    whoosh = []
    for i in range(int(rate * 0.6)):
        t = i / rate
        freq = 60 + 180 * (t / 0.6)
        env = math.sin(t / 0.6 * math.pi) * 0.35
        import random
        noise = random.uniform(-1, 1) * 0.15
        val = math.sin(2 * math.pi * freq * t) * 0.85 + noise
        whoosh.append(int(32767 * env * val))

    # Layer 2: Rising synth chord (0.2s)
    chord = []
    freqs = [220, 330, 440, 550]
    for i in range(int(rate * 1.0)):
        t = i / rate
        env = min(1.0, t * 4) * math.exp(-t * 2.8) * 0.4
        val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        chord.append(int(32767 * env * val))

    # Layer 3: Chime cascade (0.5s offset)
    chime_notes = [
        (1046.5, 0.00, 0.50),  # C6
        (1318.5, 0.08, 0.45),  # E6
        (1568.0, 0.16, 0.40),  # G6
        (2093.0, 0.24, 0.35),  # C7
        (2637.0, 0.32, 0.30),  # E7
    ]
    chime_len = int(rate * 1.2)
    chime = [0.0] * chime_len
    for freq, delay, vol in chime_notes:
        start = int(delay * rate)
        for i in range(chime_len - start):
            t = i / rate
            env = math.exp(-t * 4.5) * vol
            val = math.sin(2 * math.pi * freq * t)
            val += math.sin(2 * math.pi * freq * 2 * t) * 0.25
            chime[start + i] += 32767 * env * val
    chime = [int(x) for x in chime]

    # Mix all layers
    result = _mix(whoosh, chord, offset=int(rate * 0.2))
    result = _mix(result, chime, offset=int(rate * 0.45))
    return _wav("startup.wav", result)


def _make_angle_scan():
    """
    Short sci-fi scan beep — plays when angle capture begins.
    Rising chirp + soft tick.
    """
    rate = 44100
    chirp = _sweep(800, 2400, 0.18, vol=0.28)
    tick = _exp_decay(3200, 0.08, vol=0.15, decay=25)
    result = _mix(chirp, tick, offset=int(rate * 0.14))
    return _wav("angle_scan.wav", result)


def _make_angle_done():
    """
    Angle complete — soft positive double-ping.
    """
    rate = 44100
    p1 = _exp_decay(1200, 0.12, vol=0.30, decay=18)
    p2 = _exp_decay(1600, 0.10, vol=0.25, decay=20)
    result = _mix(p1, p2, offset=int(rate * 0.08))
    return _wav("angle_done.wav", result)


def _make_complete():
    """
    Enrollment complete — triumphant ascending arpeggio + warm pad.
    """
    rate = 44100

    # Arpeggio: C5 E5 G5 C6
    notes = [523.25, 659.25, 783.99, 1046.5]
    arp_len = int(rate * 1.2)
    arp = [0.0] * arp_len
    for idx, freq in enumerate(notes):
        start = int(idx * 0.12 * rate)
        for i in range(arp_len - start):
            t = i / rate
            env = math.exp(-t * 3.5) * 0.45
            val = math.sin(2 * math.pi * freq * t)
            val += math.sin(2 * math.pi * freq * 2 * t) * 0.2
            arp[start + i] += 32767 * env * val

    # Warm pad chord underneath
    pad = []
    pad_freqs = [261.63, 329.63, 392.0]
    for i in range(int(rate * 1.5)):
        t = i / rate
        env = min(1.0, t * 3) * math.exp(-t * 1.8) * 0.25
        val = sum(math.sin(2 * math.pi * f * t) for f in pad_freqs)
        pad.append(int(32767 * env * val / len(pad_freqs)))

    result = _mix([int(x) for x in arp], pad)
    return _wav("complete.wav", result)


def _make_error():
    """Low descending error tone."""
    rate = 44100
    s1 = _exp_decay(400, 0.15, vol=0.35, decay=8)
    s2 = _exp_decay(280, 0.20, vol=0.30, decay=6)
    result = _mix(s1, s2, offset=int(rate * 0.10))
    return _wav("error.wav", result)


def _make_ui_click():
    """Subtle UI interaction click."""
    rate = 44100
    s = _exp_decay(1800, 0.06, vol=0.18, decay=35)
    return _wav("ui_click.wav", s)


# Pre-generate all sounds at import time
try:
    SND_STARTUP    = _make_startup()
    SND_ANGLE_SCAN = _make_angle_scan()
    SND_ANGLE_DONE = _make_angle_done()
    SND_COMPLETE   = _make_complete()
    SND_ERROR      = _make_error()
    SND_CLICK      = _make_ui_click()
    _SOUNDS_OK = True
except Exception:
    _SOUNDS_OK = False
    SND_STARTUP = SND_ANGLE_SCAN = SND_ANGLE_DONE = None
    SND_COMPLETE = SND_ERROR = SND_CLICK = None


def play(path):
    """Play sound non-blocking. PulseAudio → ALSA fallback."""
    if not path or not _SOUNDS_OK:
        return
    try:
        subprocess.Popen(
            ["paplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except Exception:
        pass
    try:
        subprocess.Popen(
            ["aplay", "-q", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
