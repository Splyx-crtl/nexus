"""Composes the NEXUS soundtrack: three seamless synthwave loops, written to assets/music/*.wav.

Everything is generated from code (no samples, no third-party music), so there is nothing to license and the tracks are ours.
Run:  python tools/build_music.py         (about a minute; the result is committed, the game only plays the WAV files)
"""
from __future__ import annotations

import math
import random
import sys
import wave
from array import array
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "music"
TAU = 2 * math.pi


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


class Track:
    """One loop. All writes wrap around the end, so tails run into the start and the loop has no seam."""

    def __init__(self, bpm: float, bars: int, seed: int = 7):
        self.bpm, self.bars = bpm, bars
        self.beat = 60.0 / bpm
        self.n = int(round(bars * 4 * self.beat * RATE))
        self.rng = random.Random(seed)
        self.stems: dict[str, list[float]] = {}

    def stem(self, name: str) -> list[float]:
        return self.stems.setdefault(name, [0.0] * self.n)

    def at(self, bar: float, beat: float = 0.0) -> int:
        return int(round((bar * 4 + beat) * self.beat * RATE))

    # --------------------------------------------------------------- voices
    def tone(self, stem: str, start: int, seconds: float, freq: float, vol: float, kind: str = "saw", attack: float = 0.005,
             release: float = 0.05, decay: float = 0.0, detune: float = 0.0, pulse: float = 0.5) -> None:
        buf, n_total = self.stem(stem), self.n
        n = int(seconds * RATE)
        a, r = max(1, int(attack * RATE)), max(1, int(release * RATE))
        inc = freq * (1 + detune) / RATE
        ph = 0.0
        for i in range(n):
            ph += inc
            ph -= int(ph)
            if kind == "saw":
                s = 2.0 * ph - 1.0
            elif kind == "square":
                s = 1.0 if ph < pulse else -1.0
            elif kind == "sine":
                s = math.sin(TAU * ph)
            else:                                           # triangle
                s = 4.0 * abs(ph - 0.5) - 1.0
            env = 1.0
            if i < a:
                env = i / a
            elif i > n - r:
                env = (n - i) / r
            if decay:
                env *= math.exp(-decay * i / RATE)
            buf[(start + i) % n_total] += s * vol * env

    def kick(self, start: int, vol: float = 0.9) -> None:
        buf, n_total = self.stem("drums"), self.n
        n = int(0.28 * RATE)
        ph = 0.0
        for i in range(n):
            t = i / RATE
            f = 45 + 110 * math.exp(-t * 28)
            ph += f / RATE
            buf[(start + i) % n_total] += math.sin(TAU * ph) * vol * math.exp(-t * 11) * min(1.0, i / 30)

    def snare(self, start: int, vol: float = 0.45) -> None:
        buf, n_total = self.stem("drums"), self.n
        n = int(0.22 * RATE)
        for i in range(n):
            t = i / RATE
            noise = self.rng.random() * 2 - 1
            body = math.sin(TAU * 190 * t) * math.exp(-t * 28)
            buf[(start + i) % n_total] += (noise * math.exp(-t * 16) * 0.8 + body * 0.6) * vol

    def hat(self, start: int, vol: float = 0.18, length: float = 0.05) -> None:
        buf, n_total = self.stem("drums"), self.n
        n = int(length * RATE)
        prev = 0.0
        for i in range(n):
            noise = self.rng.random() * 2 - 1
            hp = noise - prev                                # crude high-pass: keeps only the fast changes
            prev = noise
            buf[(start + i) % n_total] += hp * vol * math.exp(-i / n * 7)

    # --------------------------------------------------------------- mixing
    def lowpass(self, name: str, cutoff: float, lfo: float = 0.0, lfo_hz: float = 0.0) -> None:
        """One-pole low-pass, run over the loop twice so the filter state at the wrap point is right."""
        buf, n = self.stem(name), self.n
        y = 0.0
        out = [0.0] * n
        for rnd in range(2):
            for i in range(n):
                c = cutoff * (1 + lfo * math.sin(TAU * lfo_hz * i / RATE)) if lfo else cutoff
                a = 1 - math.exp(-TAU * c / RATE)
                y += a * (buf[i] - y)
                if rnd:
                    out[i] = y
        self.stems[name] = out

    def echo(self, name: str, delay_beats: float, feedback: float, mix: float) -> None:
        buf, n = self.stem(name), self.n
        d = int(delay_beats * self.beat * RATE)
        out = buf[:]
        gain, shift = mix, d
        for _ in range(4):
            for i in range(n):
                out[(i + shift) % n] += buf[i] * gain
            gain *= feedback
            shift += d
        self.stems[name] = out

    def render(self, gains: dict[str, float], path: Path) -> dict:
        n = self.n
        mix = [0.0] * n
        for name, buf in self.stems.items():
            g = gains.get(name, 1.0)
            for i in range(n):
                mix[i] += buf[i] * g
        peak = max(abs(x) for x in mix) or 1.0
        scale = 0.88 / peak
        soft = [math.tanh(1.3 * x * scale) / math.tanh(1.3) for x in mix]            # gentle glue, avoids hard clipping
        path.parent.mkdir(parents=True, exist_ok=True)
        data = array("h", (int(max(-1.0, min(1.0, v)) * 30000) for v in soft))
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(data.tobytes())
        rms = math.sqrt(sum(v * v for v in soft) / n)
        return {"seconds": n / RATE, "peak": max(abs(v) for v in soft), "rms": rms, "seam": abs(soft[0] - soft[-1])}


# ------------------------------------------------------------------ music
A_MINOR = {  # chord = (bass root, [pad notes])
    "Am": (45, [57, 60, 64, 69]), "F": (41, [53, 57, 60, 65]), "C": (48, [55, 60, 64, 67]), "G": (43, [55, 59, 62, 67]),
    "Em": (40, [55, 59, 64, 67]), "E": (40, [56, 59, 64, 68]), "Dm": (38, [53, 57, 62, 65]),
}
ARP_SHAPE = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0, 1, 2, 3, 4, 3]


def pad(t: Track, chords: list[str], bars_per_chord: int, vol: float, attack: float = 0.9) -> None:
    for c, name in enumerate(chords):
        bar = c * bars_per_chord
        start, seconds = t.at(bar), bars_per_chord * 4 * t.beat
        for note in A_MINOR[name][1]:
            for detune in (-0.004, 0.004):
                t.tone("pad", start, seconds + 0.6, hz(note), vol, "saw", attack=attack, release=1.0, detune=detune)
    t.lowpass("pad", 1100, 0.45, 0.04)


def bassline(t: Track, chords: list[str], bars_per_chord: int, pattern: str, vol: float) -> None:
    """pattern: 16 chars per bar, 'x' = hit on that 16th, '-' = rest."""
    for c, name in enumerate(chords):
        root = A_MINOR[name][0]
        for b in range(bars_per_chord):
            bar = c * bars_per_chord + b
            for step, ch in enumerate(pattern):
                if ch == "x":
                    s = t.at(bar, step / 4)
                    octave = 12 if step in (6, 14) and "o" in pattern else 0
                    t.tone("bass", s, t.beat * 0.45, hz(root + octave), vol, "saw", attack=0.004, release=0.06, decay=2.5)
                    t.tone("bass", s, t.beat * 0.45, hz(root + octave - 12), vol * 0.9, "sine", attack=0.004, release=0.06, decay=2.0)
    t.lowpass("bass", 420)


def arpeggio(t: Track, chords: list[str], bars_per_chord: int, vol: float, every: int = 1, octave: int = 12) -> None:
    for c, name in enumerate(chords):
        tones = [n + octave for n in A_MINOR[name][1][:3]] + [n + octave + 12 for n in A_MINOR[name][1][:3]]
        for b in range(bars_per_chord):
            bar = c * bars_per_chord + b
            for step in range(0, 16, every):
                note = tones[ARP_SHAPE[step] % len(tones)]
                accent = 1.0 if step % 4 == 0 else 0.7
                t.tone("arp", t.at(bar, step / 4), t.beat * 0.9, hz(note), vol * accent, "square", attack=0.003, release=0.05,
                       decay=7.0, pulse=0.35)
    t.lowpass("arp", 3200)
    t.echo("arp", 0.75, 0.45, 0.5)


def drums(t: Track, bars: int, style: str) -> None:
    for bar in range(bars):
        for beat in range(4):
            if style == "drive":
                t.kick(t.at(bar, beat), 0.95)
                t.hat(t.at(bar, beat + 0.5), 0.22)
                t.hat(t.at(bar, beat + 0.25), 0.1, 0.03)
                t.hat(t.at(bar, beat + 0.75), 0.1, 0.03)
                if beat in (1, 3):
                    t.snare(t.at(bar, beat), 0.5)
            else:                                            # "calm"
                if beat in (0, 2):
                    t.kick(t.at(bar, beat), 0.7)
                if beat in (1, 3):
                    t.snare(t.at(bar, beat), 0.3)
                t.hat(t.at(bar, beat + 0.5), 0.14)


def make_menu() -> dict:
    t = Track(100, 16)
    chords = ["Am", "F", "C", "G"]
    pad(t, chords, 4, 0.05)
    bassline(t, chords, 4, "x--x--x-x--x--x-", 0.22)
    arpeggio(t, chords, 4, 0.10)
    drums(t, 16, "calm")
    return t.render({"pad": 1.0, "bass": 1.0, "arp": 1.0, "drums": 0.8}, OUT / "menu.wav")


def make_terminal() -> dict:
    t = Track(78, 16, seed=11)
    chords = ["Am", "Em", "F", "G"]
    pad(t, chords, 4, 0.06, attack=1.4)
    bassline(t, chords, 4, "x-------x-------", 0.20)
    arpeggio(t, chords, 4, 0.06, every=2, octave=24)
    return t.render({"pad": 1.0, "bass": 0.9, "arp": 0.8}, OUT / "terminal.wav")


def make_tension() -> dict:
    t = Track(124, 16, seed=3)
    chords = ["Am", "Am", "F", "E"]
    pad(t, chords, 4, 0.045, attack=0.3)
    bassline(t, chords, 4, "xx-xxx-xxx-xxx-x", 0.20)
    arpeggio(t, chords, 4, 0.10)
    drums(t, 16, "drive")
    return t.render({"pad": 0.9, "bass": 1.0, "arp": 1.0, "drums": 0.9}, OUT / "tension.wav")


def main() -> int:
    for name, fn in (("menu", make_menu), ("terminal", make_terminal), ("tension", make_tension)):
        info = fn()
        print(f"{name:9s} {info['seconds']:5.1f}s  peak {info['peak']:.2f}  rms {info['rms']:.3f}  seam {info['seam']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
