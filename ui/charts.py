"""Small painter-based charts for the statistics dashboard (no external plotting library)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from nexus.config import COLORS

from .widgets import mono_font


class _ChartBase(QWidget):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.title, self.color = title, color
        self.setMinimumSize(220, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _frame(self, p: QPainter) -> QRectF:
        p.fillRect(self.rect(), QColor(COLORS["panel"]))
        p.setPen(QPen(QColor(COLORS["border"]), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.setPen(QColor(COLORS["cyan"]))
        p.setFont(mono_font(10, True))
        p.drawText(QRectF(10, 6, self.width() - 20, 18), Qt.AlignmentFlag.AlignLeft, self.title)
        return QRectF(14, 30, self.width() - 28, self.height() - 46)

    def _empty(self, p: QPainter, area: QRectF) -> None:
        p.setPen(QColor(COLORS["dim"]))
        p.setFont(mono_font(9))
        p.drawText(area, Qt.AlignmentFlag.AlignCenter, "Not enough data yet.\nPlay a little more.")


class LineChart(_ChartBase):
    """Line chart with area fill. ``values`` are plotted evenly spaced; last value shown big."""

    def __init__(self, title: str, color: str, fmt=lambda v: f"{int(v):,}", parent=None):
        super().__init__(title, color, parent)
        self.values: list[float] = []
        self.fmt = fmt

    def set_values(self, values: list[float]) -> None:
        self.values = list(values)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self._frame(p)
        vals = self.values
        if len(vals) < 2:
            self._empty(p, area)
            return
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        for i in range(1, 4):                                           # grid
            y = area.top() + area.height() * i / 4
            p.setPen(QPen(QColor(COLORS["border"]), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        pts = [QPointF(area.left() + area.width() * i / (len(vals) - 1), area.bottom() - area.height() * (v - lo) / span * 0.9 - 4)
               for i, v in enumerate(vals)]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        fill = QPainterPath(path)
        fill.lineTo(QPointF(pts[-1].x(), area.bottom()))
        fill.lineTo(QPointF(pts[0].x(), area.bottom()))
        c = QColor(self.color)
        c.setAlpha(40)
        p.fillPath(fill, c)
        p.setPen(QPen(QColor(self.color), 2))
        p.drawPath(path)
        p.setBrush(QColor(self.color))
        p.drawEllipse(pts[-1], 4, 4)
        p.setPen(QColor(COLORS["white"]))
        p.setFont(mono_font(11, True))
        p.drawText(QRectF(area.left(), 6, area.width(), 18), Qt.AlignmentFlag.AlignRight, self.fmt(vals[-1]))


class BarChart(_ChartBase):
    """Vertical bars with labels (e.g. missions completed per type)."""

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(title, color, parent)
        self.items: list[tuple[str, float]] = []

    def set_items(self, items: list[tuple[str, float]]) -> None:
        self.items = items
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self._frame(p)
        if not self.items or max(v for _, v in self.items) <= 0:
            self._empty(p, area)
            return
        top = max(v for _, v in self.items)
        n = len(self.items)
        slot = area.width() / n
        for i, (label, value) in enumerate(self.items):
            h = (area.height() - 22) * value / top
            bar = QRectF(area.left() + i * slot + slot * 0.18, area.bottom() - 16 - h, slot * 0.64, h)
            c = QColor(self.color)
            c.setAlpha(190)
            p.fillRect(bar, c)
            p.setPen(QColor(COLORS["white"]))
            p.setFont(mono_font(8, True))
            p.drawText(QRectF(bar.left() - 6, bar.top() - 14, bar.width() + 12, 12), Qt.AlignmentFlag.AlignCenter, str(int(value)))
            p.setPen(QColor(COLORS["dim"]))
            p.setFont(mono_font(7))
            p.drawText(QRectF(area.left() + i * slot, area.bottom() - 13, slot, 12), Qt.AlignmentFlag.AlignCenter, label[:7])


class DonutChart(_ChartBase):
    """Ring showing a ratio (success rate / achievements)."""

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(title, color, parent)
        self.value, self.total, self.caption = 0.0, 0.0, ""

    def set_ratio(self, value: float, total: float, caption: str = "") -> None:
        self.value, self.total, self.caption = value, total, caption
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self._frame(p)
        size = min(area.width(), area.height()) - 6
        rect = QRectF(area.center().x() - size / 2, area.center().y() - size / 2, size, size)
        p.setPen(QPen(QColor(COLORS["border"]), 10))
        p.drawArc(rect, 0, 360 * 16)
        ratio = (self.value / self.total) if self.total else 0.0
        p.setPen(QPen(QColor(self.color), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(rect, 90 * 16, int(-360 * 16 * ratio))
        p.setPen(QColor(COLORS["white"]))
        p.setFont(mono_font(max(10, int(size / 5)), True))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{ratio * 100:.0f}%" + (f"\n{self.caption}" if self.caption else ""))


class StatTile(_ChartBase):
    """Big number tile (e.g. total playtime)."""

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(title, color, parent)
        self.text, self.sub = "—", ""

    def set_text(self, text: str, sub: str = "") -> None:
        self.text, self.sub = text, sub
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        area = self._frame(p)
        p.setPen(QColor(self.color))
        p.setFont(mono_font(22, True))
        p.drawText(area, Qt.AlignmentFlag.AlignCenter, self.text)
        if self.sub:
            p.setPen(QColor(COLORS["dim"]))
            p.setFont(mono_font(9))
            p.drawText(QRectF(area.left(), area.bottom() - 18, area.width(), 16), Qt.AlignmentFlag.AlignCenter, self.sub)
