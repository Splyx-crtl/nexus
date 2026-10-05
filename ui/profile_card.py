"""D1: the profile card / share image - a single PNG summarizing a v3 campaign profile (callsign, rank, level,
missions completed, chosen ending), meant to be posted outside the game (Discord, a forum signature, a screenshot
thread). Pure QPainter-on-a-QPixmap, no widget needed, so it can be rendered and saved without ever showing a window.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap

from nexus.campaign.endings import ENDINGS
from nexus.campaign.profile import CampaignProfile
from nexus.config import COLORS, VERSION, mask_name

CARD_W, CARD_H = 1200, 675


def render_profile_card(profile: CampaignProfile, total_missions: int = 200) -> QPixmap:
    pm = QPixmap(CARD_W, CARD_H)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    bg = QLinearGradient(0, 0, CARD_W, CARD_H)
    bg.setColorAt(0.0, QColor(COLORS["bg_alt"]))
    bg.setColorAt(1.0, QColor(COLORS["bg"]))
    p.fillRect(0, 0, CARD_W, CARD_H, bg)

    p.setPen(QPen(QColor(COLORS["border"]), 1))
    for x in range(0, CARD_W, 36):
        p.drawLine(x, 0, x, CARD_H)
    for y in range(0, CARD_H, 36):
        p.drawLine(0, y, CARD_W, y)

    p.setPen(QPen(QColor(COLORS["green"]), 3))
    p.drawRect(8, 8, CARD_W - 16, CARD_H - 16)

    def text(x, y, s, size, color, bold=True, letter_spacing=0):
        f = QFont("Consolas")
        f.setPixelSize(size)
        f.setBold(bold)
        if letter_spacing:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(x, y, s)

    text(48, 70, "NEXUS // TERMINAL", 26, COLORS["green"], letter_spacing=3)
    text(48, 102, "OPERATOR PROFILE", 14, COLORS["dim"], letter_spacing=4)

    name = mask_name(profile.get_character().get("name") or profile.username or "OPERATOR")
    text(48, 230, name.upper(), 64, COLORS["white"])
    text(48, 275, f"RANK {profile.rank}", 20, COLORS["cyan"], letter_spacing=2)

    done, total = profile.completed_count, total_missions
    text(48, 340, f"LEVEL {profile.level}", 18, COLORS["text"])
    text(48, 372, f"{done} / {total} MISSIONS COMPLETE", 18, COLORS["text"])
    text(48, 404, f"{profile.xp:,} XP", 18, COLORS["amber"])

    bar_x, bar_y, bar_w, bar_h = 48, 430, 500, 14
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(COLORS["panel_hi"]))
    p.drawRect(bar_x, bar_y, bar_w, bar_h)
    frac = min(1.0, done / total) if total else 0.0
    p.setBrush(QColor(COLORS["green"]))
    p.drawRect(bar_x, bar_y, int(bar_w * frac), bar_h)

    ending_id = profile.db.get_profile().get("ending")
    if ending_id and ending_id in ENDINGS:
        ending = ENDINGS[ending_id]
        text(48, 500, f"ENDING: {ending.title.upper()}", 20, COLORS["purple"], letter_spacing=1)
        text(48, 528, f'"{ending.subtitle}"', 15, COLORS["dim"], bold=False)
    else:
        text(48, 500, "CAMPAIGN IN PROGRESS", 20, COLORS["dim"], letter_spacing=1)

    text(48, CARD_H - 36, f"nexus // v{VERSION}", 13, COLORS["dim"], bold=False, letter_spacing=1)

    p.end()
    return pm
