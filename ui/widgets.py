"""Shared widgets and the global cyberpunk theme."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import Property, QEvent, QObject, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from nexus.config import COLORS, FONT_CANDIDATES, FONTS_DIR

C = COLORS
_sound = None


def set_sound(manager) -> None:
    global _sound
    _sound = manager


def play(name: str) -> None:
    if _sound:
        _sound.play(name)


# ---------------------------------------------------------------- fonts / theme
def load_custom_fonts() -> None:
    for path in list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf")):
        QFontDatabase.addApplicationFont(str(path))


def mono_family() -> str:
    families = set(QFontDatabase.families())
    for name in FONT_CANDIDATES:
        if name in families:
            return name
    return "monospace"


def mono_font(size: int = 12, bold: bool = False) -> QFont:
    font = QFont(mono_family(), size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(bold)
    return font


def build_stylesheet(size: int = 12) -> str:
    fam = mono_family()
    return f"""
    * {{ font-family: '{fam}'; font-size: {size}px; }}
    QWidget {{ background-color: {C['bg']}; color: {C['text']}; }}
    QMainWindow, QDialog {{ background-color: {C['bg']}; }}
    QLabel {{ background: transparent; }}
    QLabel#h1 {{ color: {C['green']}; font-size: {size + 8}px; font-weight: bold; letter-spacing: 3px; }}
    QLabel#h2 {{ color: {C['cyan']}; font-size: {size + 2}px; font-weight: bold; letter-spacing: 2px; }}
    QLabel#dim {{ color: {C['dim']}; }}
    QLabel#warn {{ color: {C['amber']}; }}
    QLabel#err {{ color: {C['red']}; }}
    QToolTip {{ background-color: {C['panel_hi']}; color: {C['green']}; border: 1px solid {C['green_dim']}; padding: 4px; }}

    QPushButton {{ background-color: {C['panel']}; color: {C['green']}; border: 1px solid {C['green_dim']};
                  padding: 6px 14px; letter-spacing: 1px; }}
    QPushButton:hover {{ background-color: {C['panel_hi']}; border: 1px solid {C['green']}; color: {C['white']}; }}
    QPushButton:pressed {{ background-color: {C['green_dim']}; color: {C['bg']}; }}
    QPushButton:disabled {{ color: {C['dim']}; border: 1px solid {C['border']}; background-color: {C['bg_alt']}; }}
    QPushButton#danger {{ color: {C['red']}; border: 1px solid #7a1d30; }}
    QPushButton#danger:hover {{ border: 1px solid {C['red']}; }}
    QPushButton#cyan {{ color: {C['cyan']}; border: 1px solid {C['cyan_dim']}; }}
    QPushButton#cyan:hover {{ border: 1px solid {C['cyan']}; }}

    QLineEdit, QSpinBox, QComboBox {{ background-color: {C['bg_alt']}; color: {C['green']}; border: 1px solid {C['border']};
                                    padding: 4px 6px; selection-background-color: {C['green_dim']}; selection-color: {C['bg']}; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {C['green']}; }}
    QComboBox QAbstractItemView {{ background-color: {C['panel']}; color: {C['green']}; selection-background-color: {C['green_dim']};
                                  border: 1px solid {C['green_dim']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}

    QTextEdit, QPlainTextEdit, QTextBrowser {{ background-color: {C['bg']}; color: {C['text']}; border: none;
                                              selection-background-color: {C['green_dim']}; selection-color: {C['bg']}; }}
    QListWidget, QTableWidget {{ background-color: {C['bg_alt']}; border: 1px solid {C['border']}; outline: none; }}
    QListWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {C['panel']}; }}
    QListWidget::item:selected {{ background-color: {C['panel_hi']}; color: {C['green']}; border-left: 3px solid {C['green']}; }}
    QListWidget::item:hover {{ background-color: {C['panel']}; }}
    QHeaderView::section {{ background-color: {C['panel']}; color: {C['cyan']}; border: none; padding: 4px; }}

    QScrollBar:vertical {{ background: {C['bg']}; width: 9px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {C['border']}; min-height: 24px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {C['green_dim']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{ background: {C['bg']}; height: 9px; }}
    QScrollBar::handle:horizontal {{ background: {C['border']}; border-radius: 4px; }}

    QTabWidget::pane {{ border: 1px solid {C['border']}; top: -1px; }}
    QTabBar::tab {{ background: {C['panel']}; color: {C['dim']}; padding: 6px 12px; border: 1px solid {C['border']};
                   border-bottom: none; margin-right: 2px; letter-spacing: 1px; }}
    QTabBar::tab:selected {{ color: {C['green']}; background: {C['panel_hi']}; border-top: 2px solid {C['green']}; }}
    QTabBar::tab:hover {{ color: {C['white']}; }}

    QSlider::groove:horizontal {{ height: 4px; background: {C['border']}; }}
    QSlider::handle:horizontal {{ background: {C['green']}; width: 14px; margin: -6px 0; }}
    QSlider::sub-page:horizontal {{ background: {C['green_dim']}; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['green_dim']}; background: {C['bg_alt']}; }}
    QCheckBox::indicator:checked {{ background: {C['green']}; }}
    QPushButton#nav {{ text-align: left; padding: 9px 14px; border: none; border-left: 3px solid transparent; background: transparent;
                      color: {C['dim']}; letter-spacing: 2px; }}
    QPushButton#nav:hover {{ color: {C['white']}; background-color: {C['panel']}; }}
    QPushButton#nav:checked {{ color: {C['green']}; background-color: {C['panel_hi']}; border-left: 3px solid {C['green']}; }}
    QPushButton#chip {{ padding: 4px 12px; border: 1px solid {C['border']}; color: {C['dim']}; background: transparent; }}
    QPushButton#chip:checked {{ color: {C['bg']}; background-color: {C['green']}; border: 1px solid {C['green']}; }}
    QPushButton#chip:hover {{ border: 1px solid {C['green']}; }}
    QFrame#card {{ background-color: {C['panel']}; border: 1px solid {C['border']}; }}
    QFrame#card:hover {{ border: 1px solid {C['green_dim']}; }}
    QFrame#panel {{ background-color: {C['panel']}; border: 1px solid {C['border']}; }}
    QFrame#toast {{ background-color: {C['panel_hi']}; border: 1px solid {C['green_dim']}; }}
    """


# ----------------------------------------------------------------- buttons etc.
class NeonButton(QPushButton):
    """Button with click sound + hover sound-free glow (styled through QSS)."""

    def __init__(self, text: str = "", tooltip: str = "", variant: str = "", parent=None):
        super().__init__(text, parent)
        if variant:
            self.setObjectName(variant)
        if tooltip:
            self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pressed.connect(lambda: play("click"))


class NeonBar(QWidget):
    """Segmented progress bar (value/maximum) with optional text."""

    def __init__(self, color: str = C["green"], segments: int = 20, height: int = 14, parent=None):
        super().__init__(parent)
        self._value, self._max, self._color, self._segments = 0.0, 100.0, QColor(color), segments
        self._text = ""
        self.setFixedHeight(height)
        self.setMinimumWidth(80)

    def set_value(self, value: float, maximum: float | None = None, text: str | None = None) -> None:
        self._value = max(0.0, value)
        if maximum is not None:
            self._max = max(1.0, maximum)
        if text is not None:
            self._text = text
        self.update()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        gap = 2
        seg_w = (w - gap * (self._segments - 1)) / self._segments
        filled = self._value / self._max * self._segments
        for i in range(self._segments):
            x = i * (seg_w + gap)
            color = QColor(self._color)
            if i + 1 > filled:
                part = max(0.0, min(1.0, filled - i))
                color.setAlphaF(0.12 + 0.88 * part)
            p.fillRect(QRectF(x, 0, seg_w, h), color)
        if self._text:
            p.setPen(QColor(C["white"]))
            f = mono_font(max(8, h - 5), True)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self._text)


class Panel(QFrame):
    """Titled panel with neon corner brackets."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        if title:
            head = QLabel(f"// {title}")
            head.setObjectName("h2")
            lay.addWidget(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(5)
        lay.addLayout(self.body)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setPen(QPen(QColor(C["green"]), 2))
        w, h, s = self.width() - 1, self.height() - 1, 10
        for x, y, dx, dy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
            p.drawLine(x, y, x + dx * s, y)
            p.drawLine(x, y, x, y + dy * s)


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {C['border']};")
    return line


class Deferred(QObject):
    """Signal slot that only does its work while ``widget`` is visible.

    Engine signals fire many times per second; rebuilding a page nobody is looking at is wasted time. A hidden page
    just remembers that it is stale and refreshes once, the moment it is shown."""

    def __init__(self, widget: QWidget, fn):
        super().__init__(widget)
        self._widget, self._fn, self.stale = widget, fn, True
        widget.installEventFilter(self)

    def __call__(self, *_args) -> None:
        if self._widget.isVisible():
            self.stale = False
            self._fn()
        else:
            self.stale = True

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and self.stale:
            self.stale = False
            self._fn()
        return False


# --------------------------------------------------------------------- overlays
class ScanlineOverlay(QWidget):
    """CRT scanlines + vignette + refresh band, plus glitch bursts and a red alert pulse. Click-through.

    Performance: this widget covers the whole window, so every repaint of it also repaints everything below it.
    The static layers (scanlines, vignette, alert glow) are therefore rendered once into cached pixmaps, and the
    moving refresh band only invalidates its own stripe. Nothing is repainted while there is nothing to animate.
    """

    BAND_H = 90

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._band = 0.0
        self.show_lines = True
        self.alert = False
        self._pulse = 0.0
        self._glitch = 0
        self.rng = random.Random()
        self._static: QPixmap | None = None      # scanlines + vignette
        self._glow: QPixmap | None = None        # red alert vignette (full alpha, faded with setOpacity)
        self._cache_key: tuple = ()
        self._timer = QTimer(self, interval=60)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        parent.installEventFilter(self)
        self.resize(parent.size())

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == ev.Type.Resize:
            self.resize(obj.size())
            self.raise_()
        return False

    def glitch(self, frames: int = 6) -> None:
        self._glitch = frames
        self.update()

    def _band_rect(self) -> QRect:
        y = int((self._band - 0.1) * self.height())
        return QRect(0, y, self.width(), self.BAND_H)

    def _tick(self):
        if not self.isVisible():
            return
        old = self._band_rect()
        self._band = (self._band + 0.006) % 1.2
        self._pulse = (self._pulse + 0.2) % (2 * math.pi)
        if self._glitch:
            self._glitch -= 1
            self.update()
        elif self.alert:
            self._alert_tick = not getattr(self, "_alert_tick", False)
            if self._alert_tick:                         # the red pulse is slow: every other frame is plenty
                self.update()
        elif self.show_lines:
            self.update(old.united(self._band_rect()))      # only the stripe the band moved through

    def _build_cache(self) -> None:
        w, h = self.width(), self.height()
        dpr = self.devicePixelRatioF()
        key = (w, h, dpr)
        if key == self._cache_key:
            return
        self._cache_key = key

        def layer() -> QPixmap:
            pm = QPixmap(int(w * dpr), int(h * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            return pm

        pm = layer()
        p = QPainter(pm)
        p.setPen(QPen(QColor(0, 0, 0, 38), 1))
        for y in range(0, h, 3):
            p.drawLine(0, y, w, y)
        vg = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.75)
        vg.setColorAt(0.6, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(0, 0, w, h, vg)
        p.end()
        self._static = pm
        pm = layer()
        p = QPainter(pm)
        vg = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.7)
        vg.setColorAt(0.55, QColor(255, 56, 96, 0))
        vg.setColorAt(1.0, QColor(255, 56, 96, 100))
        p.fillRect(0, 0, w, h, vg)
        p.end()
        self._glow = pm

    def paintEvent(self, ev):
        w, h = self.width(), self.height()
        self._build_cache()
        p = QPainter(self)
        clip = ev.rect()
        if self.show_lines:
            r = self._static.devicePixelRatio()
            p.drawPixmap(clip, self._static, QRect(int(clip.x() * r), int(clip.y() * r), int(clip.width() * r), int(clip.height() * r)))
            band_y = (self._band - 0.1) * h
            grad = QLinearGradient(0, band_y, 0, band_y + self.BAND_H)
            band = QColor(C["green"])
            grad.setColorAt(0, QColor(band.red(), band.green(), band.blue(), 0))
            grad.setColorAt(0.5, QColor(band.red(), band.green(), band.blue(), 12))
            grad.setColorAt(1, QColor(band.red(), band.green(), band.blue(), 0))
            p.fillRect(0, int(band_y), w, self.BAND_H, grad)
        if self.alert:
            p.setOpacity((60 + 40 * math.sin(self._pulse)) / 100)
            p.drawPixmap(0, 0, self._glow)
            p.setOpacity(1.0)
        if self._glitch:
            for _i in range(7):
                y = self.rng.randrange(h)
                bar_h = self.rng.randint(4, 26)
                col = QColor(255, 56, 96, 55) if self.rng.random() < 0.5 else QColor(34, 211, 238, 55)
                p.fillRect(self.rng.randint(-20, 30), y, w, bar_h, col)


class Toast(QFrame):
    ACCENT = {"info": C["cyan"], "warn": C["amber"], "ok": C["green"], "err": C["red"], "achievement": C["amber"]}

    def __init__(self, kind: str, title: str, text: str, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        accent = self.ACCENT.get(kind, C["cyan"])
        self.setStyleSheet(f"QFrame#toast {{ background:{C['panel_hi']}; border:1px solid {accent}; border-left: 4px solid {accent}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        prefix = "★ " if kind == "achievement" else ""
        head = QLabel(prefix + title)
        head.setStyleSheet(f"color:{accent}; font-weight:bold; background:transparent;")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(f"color:{C['text']}; background:transparent;")
        lay.addWidget(head)
        lay.addWidget(body)
        self.setFixedWidth(320)
        self.adjustSize()
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)


class ToastManager:
    """Stacks toasts in the top-right corner of a host widget."""

    def __init__(self, host: QWidget, top_offset: int = 64):
        self.host = host
        self.top_offset = top_offset
        self.toasts: list[Toast] = []

    def show(self, kind: str, title: str, text: str, ms: int = 3800) -> None:
        toast = Toast(kind, title, text, self.host)
        toast.show()
        toast.raise_()
        self.toasts.append(toast)
        self.layout()
        slide = QPropertyAnimation(toast, b"pos", toast)               # slide in from the right
        slide.setDuration(260)
        slide.setStartValue(toast.pos() + QPoint(60, 0))
        slide.setEndValue(toast.pos())
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start()
        toast._slide = slide
        fade = QPropertyAnimation(toast.effect, b"opacity", toast)
        fade.setDuration(500)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(lambda t=toast: self._remove(t))
        QTimer.singleShot(ms, fade.start)
        toast._fade = fade   # keep a reference
        if len(self.toasts) > 3:
            self._remove(self.toasts[0])

    def _remove(self, toast: Toast) -> None:
        if toast in self.toasts:
            self.toasts.remove(toast)
            toast.hide()
            toast.deleteLater()
            self.layout()

    def layout(self) -> None:
        y = self.top_offset
        for toast in self.toasts:
            if getattr(toast, "_slide", None) and toast._slide.state() == toast._slide.State.Running:
                y += toast.height() + 8
                continue
            toast.move(self.host.width() - toast.width() - 16, y)
            toast.raise_()
            y += toast.height() + 8


class BannerOverlay(QWidget):
    """Full-screen cinematic banner for big moments (mission complete, ZERO joins, blackout...)."""

    finished = Signal()
    THEMES = {
        "complete": (C["green"], C["cyan"]),
        "zero": (C["red"], C["cyan"]),
        "alert": (C["amber"], C["red"]),
        "failure": (C["red"], C["amber"]),
        "critical": (C["red"], C["amber"]),
        "blackout": (C["white"], C["cyan"]),
        "achievement": (C["amber"], C["green"]),
        "levelup": (C["amber"], C["green"]),
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.hide()
        self.queue: list[tuple[str, list[str]]] = []
        self.kind, self.lines = "alert", []
        self.reveal = 0.0
        self.hold = 0.0
        self.alpha = 0.0
        self.fading = False
        self.shake = 0.0
        self.glitch_enabled = True
        self.sound_cb = None
        self.rng = random.Random()
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        parent.installEventFilter(self)

    @property
    def active(self) -> bool:
        return self.isVisible()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == ev.Type.Resize:
            self.resize(obj.size())
        return False

    def push(self, kind: str, lines: list[str]) -> None:
        self.queue.append((kind, [l for l in lines if l is not None]))
        if not self.active:
            self._next()

    def _next(self) -> None:
        if not self.queue:
            self.hide()
            self.timer.stop()
            self.finished.emit()
            return
        self.kind, self.lines = self.queue.pop(0)
        self.reveal, self.hold, self.alpha, self.fading = 0.0, 0.0, 0.0, False
        self.shake = 1.0 if self.kind in ("critical", "failure", "zero") else 0.3
        self.resize(self.parent().size())
        self.raise_()
        self.show()
        self.setFocus()
        self.timer.start()
        if self.sound_cb:
            self.sound_cb({"complete": "complete", "achievement": "achievement", "failure": "error", "zero": "glitch", "levelup": "achievement"}.get(self.kind, "warning"))

    def total_chars(self) -> int:
        return sum(len(l) for l in self.lines)

    def _tick(self) -> None:
        dt = 0.033
        self.shake = max(0.0, self.shake - dt * 0.5)
        if self.fading:                                   # fade-out: alpha must only go down here (it used to be pushed back
            self.alpha = max(0.0, self.alpha - dt * 3.5)  # up by the fade-in every frame, so banners never disappeared)
            if self.alpha <= 0:
                self._next()
                return
        else:
            self.alpha = min(1.0, self.alpha + dt * 4)
            if self.reveal < self.total_chars():
                self.reveal += dt * 38
                if self.sound_cb and self.rng.random() < 0.35:
                    self.sound_cb("type")
            else:
                self.hold += dt
                if self.hold > (3.2 if self.kind in ("complete", "critical", "blackout") else 2.4):
                    self.fading = True
        self.update()

    def mousePressEvent(self, _):
        self._skip()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._skip()

    def _skip(self) -> None:
        if self.reveal < self.total_chars():
            self.reveal = self.total_chars()
        else:
            self.hold = 99

    def paintEvent(self, _):
        p = QPainter(self)
        main, accent = (QColor(c) for c in self.THEMES.get(self.kind, self.THEMES["alert"]))
        w, h = self.width(), self.height()
        base = QColor(0, 0, 0, int(215 * self.alpha)) if self.kind != "blackout" else QColor(0, 0, 0, int(250 * self.alpha))
        p.fillRect(self.rect(), base)
        glow = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.6)
        tint = QColor(main)
        tint.setAlpha(int(40 * self.alpha))
        glow.setColorAt(0, tint)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), glow)

        if self.kind == "levelup":                                      # expanding rings behind the text
            t = (self.reveal + self.hold * 40) / 30.0
            for k in range(4):
                phase = (t - k * 0.35) % 1.4
                radius = phase * min(w, h) * 0.55
                ring = QColor(main)
                ring.setAlpha(int(max(0, 150 * (1 - phase / 1.4)) * self.alpha))
                p.setPen(QPen(ring, 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(w / 2, h / 2), radius, radius)
        # frame lines
        p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), int(160 * self.alpha)), 2))
        p.drawLine(int(w * 0.1), int(h * 0.30), int(w * 0.9), int(h * 0.30))
        p.drawLine(int(w * 0.1), int(h * 0.70), int(w * 0.9), int(h * 0.70))

        n = len(self.lines)
        remaining = int(self.reveal)
        line_h = h * 0.4 / max(n, 3)
        y0 = h * 0.5 - (n - 1) * line_h / 2
        jitter = self.shake * 8
        for i, line in enumerate(self.lines):
            visible = line[:remaining] if remaining < len(line) else line
            remaining = max(0, remaining - len(line))
            size = int(min(h * 0.07, w * 0.055)) if i == 0 else int(min(h * 0.04, w * 0.03))
            font = mono_font(max(10, size), True)
            p.setFont(font)
            y = y0 + i * line_h
            rect = QRectF(0, y - line_h / 2, w, line_h)
            color = main if i == 0 else (accent if line.startswith(("+", ">")) else QColor(C["white"]))
            if line.startswith("ACHIEVEMENT"):
                color = QColor(C["amber"])
            if "█" in line:
                self._draw_bar(p, rect, line, main, remaining_ratio=min(1.0, self.reveal / max(1, self.total_chars())))
                continue
            if self.glitch_enabled and i == 0 and (self.shake > 0.05 or self.rng.random() < 0.06):
                dx = self.rng.uniform(-jitter, jitter) - 3
                p.setPen(QColor(255, 56, 96, int(130 * self.alpha)))
                p.drawText(rect.translated(dx, 0), Qt.AlignmentFlag.AlignCenter, visible)
                p.setPen(QColor(34, 211, 238, int(130 * self.alpha)))
                p.drawText(rect.translated(-dx, 0), Qt.AlignmentFlag.AlignCenter, visible)
            col = QColor(color)
            col.setAlpha(int(255 * self.alpha))
            p.setPen(col)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, visible)

    def _draw_bar(self, p: QPainter, rect: QRectF, line: str, color: QColor, remaining_ratio: float) -> None:
        bw, bh = rect.width() * 0.5, rect.height() * 0.35
        x, y = rect.center().x() - bw / 2, rect.center().y() - bh / 2
        p.setPen(QPen(color, 2))
        p.drawRect(QRectF(x, y, bw, bh))
        fill = bw * min(1.0, (self.reveal / max(1, self.total_chars())) * 1.15)
        c = QColor(color)
        c.setAlpha(int(230 * self.alpha))
        p.fillRect(QRectF(x + 3, y + 3, max(0, fill - 6), bh - 6), c)
        p.setPen(QColor(C["white"]))
        p.setFont(mono_font(max(10, int(bh * 0.6)), True))
        p.drawText(QRectF(x, y, bw, bh), Qt.AlignmentFlag.AlignCenter, f"{int(min(100, fill / bw * 100))}%")


class FadeOverlay(QWidget):
    """Black fade used for screen transitions."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._alpha = 0.0
        self.hide()
        self._anim = QPropertyAnimation(self, b"alpha", self)
        parent.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == ev.Type.Resize:
            self.resize(obj.size())
        return False

    def get_alpha(self) -> float:
        return self._alpha

    def set_alpha(self, value: float) -> None:
        self._alpha = value
        self.update()

    alpha = Property(float, get_alpha, set_alpha)

    def transition(self, middle_callback, ms: int = 220) -> None:
        self.resize(self.parent().size())
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)

        def midpoint():
            self._anim.finished.disconnect(midpoint)
            middle_callback()
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.finished.connect(done)
            self._anim.start()

        def done():
            self._anim.finished.disconnect(done)
            self.hide()

        self._anim.finished.connect(midpoint)
        self._anim.start()

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, int(255 * self._alpha)))


class GlitchTitle(QWidget):
    """Big glowing title with occasional RGB-split glitch."""

    def __init__(self, text: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.text, self.subtitle = text, subtitle
        self.glitch = 0
        self.rng = random.Random()
        self.enabled = True
        self._cache: QPixmap | None = None
        self._cache_key: tuple = ()
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.timer = QTimer(self, interval=70)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def sizeHint(self):
        return QSize(980, 190)

    def _tick(self):
        if not self.isVisible():
            return
        was = self.glitch
        if self.glitch > 0:
            self.glitch -= 1
        elif self.enabled and self.rng.random() < 0.04:
            self.glitch = self.rng.randint(2, 6)
        if was or self.glitch:                       # idle frames need no repaint: the title is a cached pixmap
            self.update()

    def _title_layout(self) -> tuple[int, QFont, QRectF]:
        w, h = self.width(), self.height()
        size = max(36, min(int(h * 0.55), int(w / (len(self.text) * 0.75))))
        font = mono_font(size, True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, size * 0.25)
        return size, font, QRectF(0, 0, w, h * 0.72)

    def _render_static(self) -> QPixmap:
        """Glow + title + subtitle, drawn once per size/theme instead of 15 drawText calls every frame."""
        w, h = self.width(), self.height()
        dpr = self.devicePixelRatioF()
        key = (w, h, dpr, C["green"], C["cyan"], self.text, self.subtitle)
        if self._cache is not None and self._cache_key == key:
            return self._cache
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        size, font, rect = self._title_layout()
        p.setFont(font)
        glow = QColor(C["green"])
        for spread, alpha in ((6, 18), (3, 30)):                    # cheap glow
            p.setPen(QColor(glow.red(), glow.green(), glow.blue(), alpha))
            for ox, oy in ((-spread, 0), (spread, 0), (0, -spread), (0, spread)):
                p.drawText(rect.translated(ox, oy), Qt.AlignmentFlag.AlignCenter, self.text)
        p.setPen(QColor(C["green"]))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
        if self.subtitle:
            sub = mono_font(max(9, size // 6))
            sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(2, size // 22))
            p.setFont(sub)
            p.setPen(QColor(C["cyan"]))
            p.drawText(QRectF(0, h * 0.70, w, h * 0.28), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.subtitle)
        p.end()
        self._cache, self._cache_key = pm, key
        return pm

    def paintEvent(self, _):
        p = QPainter(self)
        if self.glitch:
            size, font, rect = self._title_layout()
            p.setFont(font)
            dx = self.rng.randint(4, 12)
            p.setPen(QColor(255, 56, 96, 150))
            p.drawText(rect.translated(-dx, self.rng.randint(-2, 2)), Qt.AlignmentFlag.AlignCenter, self.text)
            p.setPen(QColor(34, 211, 238, 150))
            p.drawText(rect.translated(dx, self.rng.randint(-2, 2)), Qt.AlignmentFlag.AlignCenter, self.text)
        p.drawPixmap(0, 0, self._render_static())


def labeled_row(label: str, widget: QWidget, hint: str = "") -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    name = QLabel(label)
    name.setMinimumWidth(170)
    if hint:
        name.setToolTip(hint)
    lay.addWidget(name)
    lay.addWidget(widget, 1)
    return row


# ------------------------------------------------------------------ v2 widgets
def rarity_color(rarity: str) -> str:
    return {"COMMON": C["text"], "UNCOMMON": C["green"], "RARE": C["cyan"], "EPIC": C["purple"],
            "LEGENDARY": C["amber"], "NEXUS": "#ffffff"}.get(rarity.upper(), C["text"])


CATEGORY_GLYPH = {"TOOLS": "T", "UPGRADES": "U", "COSMETICS": "C", "ACCESS": "A", "INTELLIGENCE": "I", "SPECIAL": "S"}


class ItemIcon(QWidget):
    """Hexagonal item icon: category initial in a rarity-coloured frame (font independent)."""

    def __init__(self, category: str = "TOOLS", rarity: str = "COMMON", size: int = 44, parent=None, glyph: str | None = None):
        super().__init__(parent)
        self.category, self.rarity, self.glyph = category, rarity, glyph
        self.setFixedSize(size, size)

    def set_item(self, category: str, rarity: str, glyph: str | None = None) -> None:
        self.category, self.rarity, self.glyph = category, rarity, glyph
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(rarity_color(self.rarity))
        cx, cy, r = self.width() / 2, self.height() / 2, min(self.width(), self.height()) / 2 - 3
        from PySide6.QtGui import QPolygonF
        poly = QPolygonF([QPointF(cx + r * math.cos(math.radians(60 * i - 30)), cy + r * math.sin(math.radians(60 * i - 30))) for i in range(6)])
        fill = QColor(color)
        fill.setAlpha(36)
        p.setBrush(fill)
        p.setPen(QPen(color, 2))
        p.drawPolygon(poly)
        p.setPen(color)
        p.setFont(mono_font(max(9, int(r * 0.9)), True))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.glyph or CATEGORY_GLYPH.get(self.category, "?"))


class NavButton(QPushButton):
    """Sidebar navigation entry (checkable, optional badge)."""

    def __init__(self, text: str, tooltip: str = "", parent=None):
        super().__init__(text, parent)
        self._base = text
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.pressed.connect(lambda: play("click"))

    def set_badge(self, n: int) -> None:
        self.setText(f"{self._base}   ● {n}" if n else self._base)

    def set_label(self, text: str) -> None:
        self._base = text
        self.setText(text)


class Chip(QPushButton):
    """Small checkable filter button."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pressed.connect(lambda: play("click"))


class StatCard(QFrame):
    """Title + big value (+ optional bar) for the top bar and profile page."""

    def __init__(self, title: str, bar_color: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("dim")
        self.value = QLabel("—")
        self.value.setStyleSheet(f"color:{C['green']}; font-weight:bold; font-size: 13px;")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        self.bar = None
        if bar_color:
            self.bar = NeonBar(bar_color, 20, 6)
            lay.addWidget(self.bar)

    def set(self, value: str, bar: tuple[float, float] | None = None, color: str | None = None) -> None:
        self.value.setText(value)
        if color:
            self.value.setStyleSheet(f"color:{color}; font-weight:bold; font-size: 13px;")
        if self.bar and bar:
            self.bar.set_value(bar[0], bar[1])
