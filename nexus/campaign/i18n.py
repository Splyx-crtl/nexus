"""Mission-content translations, layered on top of the English originals rather than built into them. English stays
the single source of truth in act1.py..act9.py (nothing there changes); a translation is a sparse overlay keyed by
mission id, applied at read time by ``localize()``. Missing a mission, a field, or a whole language falls back to
English silently — translating "blockweise" (one act at a time, per docs/3.0-PROGRESS.md's plan) never leaves a
half-translated mission broken or blank.

Registering a translation (see translations/de_act1.py for the first real block; nexus/campaign/translations/__init__.py
imports every block so merely importing that package populates this registry):

    from nexus.campaign.i18n import register
    register("act1_m01", "de", title="...", briefing=["..."], debrief=["..."],
             objectives=[{"text": "...", "hints": ["...", "...", "..."]}])

``objectives`` is positional — entry ``i`` translates ``mission.objectives[i]``; an entry can omit ``hints`` (or be
``None``/omitted entirely) to fall back to the English objective text/hints for just that one objective. Reference
``solution`` command lines are never translated — they are literal shell input, not narrative text.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from .mission import Mission

TRANSLATIONS: dict[str, dict[str, dict[str, Any]]] = {}      # mission_id -> lang -> {title, briefing, debrief, objectives}


def register(mission_id: str, lang: str, title: str | None = None, briefing: list[str] | None = None,
            debrief: list[str] | None = None, objectives: list[dict | None] | None = None) -> None:
    fields: dict[str, Any] = {}
    if title is not None:
        fields["title"] = title
    if briefing is not None:
        fields["briefing"] = briefing
    if debrief is not None:
        fields["debrief"] = debrief
    if objectives is not None:
        fields["objectives"] = objectives
    TRANSLATIONS.setdefault(mission_id, {})[lang] = fields


def localize(mission: Mission, lang: str) -> Mission:
    """Returns ``mission`` unchanged if ``lang`` is English or nothing is registered for it; otherwise a copy with
    whatever fields a translation actually supplies substituted in, English filling every gap."""
    if lang == "en":
        return mission
    tr = TRANSLATIONS.get(mission.id, {}).get(lang)
    if not tr:
        return mission
    objectives = mission.objectives
    tr_objs = tr.get("objectives")
    if tr_objs:
        objectives = [
            replace(o, text=entry.get("text", o.text), hints=entry.get("hints", o.hints)) if entry else o
            for o, entry in ((o, tr_objs[i] if i < len(tr_objs) else None) for i, o in enumerate(objectives))
        ]
    return replace(mission, title=tr.get("title", mission.title), briefing=tr.get("briefing", mission.briefing),
                   debrief=tr.get("debrief", mission.debrief), objectives=objectives)
