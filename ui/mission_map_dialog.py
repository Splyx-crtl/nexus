"""D1: the mission map as a graph - a single-screen visualization of campaign progress across all 9 acts / 200
missions, distinct from MissionSelectDialog's plain replay list. Read-only (hover for details); picking a mission
to replay already has its own dedicated dialog.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import QDialog, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QVBoxLayout

from nexus.campaign.mission import Mission
from nexus.campaign.profile import CampaignProfile
from nexus.config import COLORS

NODE_SIZE = 16
NODE_SPACING = 26
ROW_SPACING = 54
LABEL_W = 90


class MissionMapDialog(QDialog):
    def __init__(self, all_missions: list[Mission], profile: CampaignProfile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mission Map")
        self.resize(900, 640)
        self.setStyleSheet(f"QDialog {{ background:{COLORS['bg']}; }}")
        lay = QVBoxLayout(self)

        scene = QGraphicsScene(self)
        view = QGraphicsView(scene)
        view.setRenderHint(view.renderHints().Antialiasing)
        view.setStyleSheet(f"background:{COLORS['bg']}; border:1px solid {COLORS['border']};")
        lay.addWidget(view, 1)
        self.scene = scene
        self.view = view

        done = profile.completed_mission_ids()
        next_mission = profile.next_mission(all_missions)
        next_id = next_mission.id if next_mission else None

        by_act: dict[int, list[Mission]] = {}
        for m in sorted(all_missions, key=lambda m: m.number):
            by_act.setdefault(m.act, []).append(m)

        for row, act in enumerate(sorted(by_act)):
            y = row * ROW_SPACING
            label = QGraphicsSimpleTextItem(f"ACT {act}")
            label.setBrush(QBrush(QColor(COLORS["dim"])))
            f = QFont("Consolas")
            f.setPixelSize(11)
            f.setBold(True)
            label.setFont(f)
            label.setPos(0, y - 6)
            scene.addItem(label)

            missions = by_act[act]
            prev_center = None
            for col, m in enumerate(missions):
                cx = LABEL_W + col * NODE_SPACING + NODE_SIZE / 2
                cy = y
                if prev_center is not None:
                    line = scene.addLine(prev_center[0], prev_center[1], cx, cy, QPen(QColor(COLORS["border"]), 1))
                    line.setZValue(-1)
                prev_center = (cx, cy)

                is_done = m.id in done
                is_next = m.id == next_id
                is_milestone = m.size == "milestone"
                rect = QRectF(cx - NODE_SIZE / 2, cy - NODE_SIZE / 2, NODE_SIZE, NODE_SIZE)
                if is_done:
                    fill, pen_color = COLORS["green"], COLORS["green"]
                elif is_next:
                    fill, pen_color = COLORS["amber"], COLORS["amber"]
                else:
                    fill, pen_color = COLORS["panel_hi"], COLORS["border"]

                item = (QGraphicsRectItem(rect) if is_milestone else QGraphicsEllipseItem(rect))
                item.setBrush(QBrush(QColor(fill)))
                item.setPen(QPen(QColor(pen_color), 2 if is_next else 1))
                status = "complete" if is_done else ("up next" if is_next else "locked")
                item.setToolTip(f"LEVEL {m.number} — {m.title}\n[{m.size}] · {status}")
                item.setData(0, m.id)
                item.setData(1, status)
                scene.addItem(item)

        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
