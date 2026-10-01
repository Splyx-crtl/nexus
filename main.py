"""NEXUS // TERMINAL — entry point.

Run with:  python main.py
This is a self-contained simulation. No real network access is ever performed.
"""
from __future__ import annotations

import sys
import traceback

from nexus.config import APP_FULL_NAME, ERROR_LOG


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from nexus.audio import SoundManager
    from nexus.save_system import SaveSystem, SettingsStore
    from ui.main_window import MainWindow
    from ui.widgets import build_stylesheet, load_custom_fonts

    app = QApplication(sys.argv)
    app.setApplicationName(APP_FULL_NAME)
    load_custom_fonts()
    settings = SettingsStore()
    app.setStyleSheet(build_stylesheet(int(settings.get("font_size"))))
    try:
        saves = SaveSystem()
        sound = SoundManager(settings)
        window = MainWindow(settings, saves, sound)
    except Exception as exc:                       # data / save-folder problems: explain instead of crashing silently
        QMessageBox.critical(None, APP_FULL_NAME, f"NEXUS could not start:\n\n{exc}")
        return 1
    window.show()
    window.startup()

    def excepthook(exc_type, exc, tb):
        try:
            ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
            with ERROR_LOG.open("a", encoding="utf-8") as fh:
                fh.write("".join(traceback.format_exception(exc_type, exc, tb)) + "\n")
        except OSError:
            pass
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = excepthook
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
