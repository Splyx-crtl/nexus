"""Audio smoke test with the real Qt backend (not part of the unittest run: CI machines have no sound device).

Run:  set QT_QPA_PLATFORM=windows  &  .venv\Scripts\python tests/ui_audio.py
Checks that effects and music load (this caught setLoopCount(QSoundEffect.Infinite) silently disabling ALL sound on newer PySide6)
and that the music crossfades between moods.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("NEXUS_NO_AUDIO", None)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from nexus.audio import SoundManager  # noqa: E402


class Settings:
    values = {"volume_master": 80, "volume_music": 70, "volume_sfx": 80, "typing_sound": True}

    def get(self, key):
        return self.values[key]


sm = SoundManager(Settings())
failures = []


def check(cond, msg):
    print(("ok: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


check(sm.enabled and len(sm.effects) >= 12, "effects loaded (audio enabled)")
check(set(sm.music) == {"menu", "terminal", "tension"}, "all three music tracks loaded")
sm.set_music("menu")
sm.play("levelup")
QTimer.singleShot(1800, lambda: check(sm.music["menu"].isPlaying() and sm.level["menu"] == 1.0, "menu music fades in and plays"))
QTimer.singleShot(2000, lambda: sm.set_music("tension"))
QTimer.singleShot(4300, lambda: (check(sm.music["tension"].isPlaying() and not sm.music["menu"].isPlaying(), "crossfade to the tension track"),
                                 app.quit()))
app.exec()
print("AUDIO FAILED" if failures else "AUDIO OK")
sys.exit(1 if failures else 0)
