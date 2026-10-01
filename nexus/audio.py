"""Sound effects. Sounds are synthesised on first run (no asset files required).

Drop your own ``<name>.wav`` files into assets/sounds to override any effect.
If audio is unavailable the game simply stays silent.
"""
from __future__ import annotations

import math
import os
import random
import struct
import wave
from pathlib import Path

from .config import SOUNDS_DIR, USER_SOUNDS_DIR

RATE = 22050


def _tone(freq: float, dur: float, vol: float = 0.5, shape: str = "sine", decay: float = 6.0) -> list[float]:
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        phase = 2 * math.pi * freq * t
        s = math.sin(phase) if shape == "sine" else (1.0 if math.sin(phase) >= 0 else -1.0)
        env = math.exp(-decay * t / max(dur, 1e-3)) * min(1.0, i / 80)
        out.append(s * vol * env)
    return out


def _sweep(f0: float, f1: float, dur: float, vol: float = 0.4, tremolo: float = 0.0) -> list[float]:
    n, out, phase = int(RATE * dur), [], 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * i / n
        phase += 2 * math.pi * f / RATE
        env = math.sin(math.pi * i / n)
        trem = 1 - tremolo + tremolo * math.sin(2 * math.pi * 30 * i / RATE)
        out.append(math.sin(phase) * vol * env * trem)
    return out


def _noise(dur: float, vol: float = 0.3, decay: float = 8.0, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    n = int(RATE * dur)
    return [(rng.random() * 2 - 1) * vol * math.exp(-decay * i / n) for i in range(n)]


def _gap(dur: float) -> list[float]:
    return [0.0] * int(RATE * dur)


def _mix(*parts: list[float]) -> list[float]:
    length = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(length)]


def _build_sounds() -> dict[str, list[float]]:
    sounds = {
        "click": _tone(1800, 0.04, 0.35, decay=8),
        "type": _mix(_noise(0.025, 0.25, 9, 3), _tone(950, 0.025, 0.12, decay=8)),
        "error": _tone(170, 0.14, 0.45, "square") + _gap(0.03) + _tone(120, 0.22, 0.45, "square"),
        "notify": _tone(880, 0.09, 0.4) + _tone(1320, 0.16, 0.4),
        "warning": sum((_tone(700, 0.09, 0.4, "square", 3) + _gap(0.07) for _ in range(3)), []),
        "complete": sum((_tone(f, 0.13, 0.4, decay=3) for f in (523, 659, 784, 1047)), []) + _tone(1047, 0.35, 0.35, decay=4),
        "achievement": sum((_tone(f, 0.08, 0.35, decay=3) for f in (660, 880, 990, 1320, 1760)), []) + _tone(1760, 0.3, 0.3, decay=5),
        "connect": _sweep(300, 900, 0.35, 0.35, 0.4),
        "glitch": _noise(0.08, 0.4, 2, 5) + _gap(0.02) + _noise(0.05, 0.35, 2, 6) + _tone(90, 0.1, 0.3, "square"),
        "boot": _sweep(70, 420, 0.7, 0.45),
    }
    # seamless 8 s ambient drone (integer cycle counts -> clean loop)
    n = RATE * 8
    sounds["ambient"] = [
        0.18 * math.sin(2 * math.pi * 55 * i / RATE) + 0.10 * math.sin(2 * math.pi * 82.5 * i / RATE)
        + 0.07 * math.sin(2 * math.pi * 110 * i / RATE) * (0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * i / RATE))
        for i in range(n)
    ]
    return sounds


def _write_wav(path: Path, samples: list[float]) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples))


def ensure_sound_files() -> dict[str, Path]:
    """Return {name: path}; synthesise any missing effect into the user sound dir."""
    found: dict[str, Path] = {}
    missing = []
    names = ["click", "type", "error", "notify", "warning", "complete", "achievement", "connect", "glitch", "boot", "ambient"]
    for name in names:
        for base in (SOUNDS_DIR, USER_SOUNDS_DIR):
            candidate = base / f"{name}.wav"
            if candidate.exists():
                found[name] = candidate
                break
        else:
            missing.append(name)
    if missing:
        try:
            USER_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
            built = _build_sounds()
            for name in missing:
                path = USER_SOUNDS_DIR / f"{name}.wav"
                _write_wav(path, built[name])
                found[name] = path
        except OSError:
            pass
    return found


class SoundManager:
    """Thin wrapper around QSoundEffect with volume control and graceful fallback."""

    POOL = {"type": 3, "click": 3}

    def __init__(self, settings=None):
        self.settings = settings
        self.effects: dict[str, list] = {}
        self.enabled = not os.environ.get("NEXUS_NO_AUDIO")
        self._rr: dict[str, int] = {}
        if not self.enabled:
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            for name, path in ensure_sound_files().items():
                pool = []
                for _ in range(self.POOL.get(name, 1)):
                    fx = QSoundEffect()
                    fx.setSource(QUrl.fromLocalFile(str(path)))
                    if name == "ambient":
                        fx.setLoopCount(QSoundEffect.Infinite)
                    pool.append(fx)
                self.effects[name] = pool
        except Exception:                      # no audio backend: stay silent
            self.enabled = False
            self.effects = {}
        self.apply_volumes()

    def _vol(self, key: str) -> float:
        if not self.settings:
            return 0.5
        return self.settings.get("volume_master") / 100 * self.settings.get(key) / 100

    def apply_volumes(self) -> None:
        for name, pool in self.effects.items():
            vol = self._vol("volume_music" if name == "ambient" else "volume_sfx")
            for fx in pool:
                fx.setVolume(vol)

    def play(self, name: str) -> None:
        pool = self.effects.get(name)
        if not pool or name == "ambient":
            return
        if name == "type" and self.settings and not self.settings.get("typing_sound"):
            return
        i = self._rr.get(name, 0)
        self._rr[name] = (i + 1) % len(pool)
        try:
            pool[i].play()
        except Exception:
            pass

    def start_ambient(self) -> None:
        pool = self.effects.get("ambient")
        if pool and not pool[0].isPlaying():
            pool[0].play()

    def stop_ambient(self) -> None:
        pool = self.effects.get("ambient")
        if pool:
            pool[0].stop()
