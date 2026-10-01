"""Minimal EN/DE localisation for the interface chrome (menus, navigation, headings)."""
from __future__ import annotations

_LANG = "en"

STRINGS: dict[str, dict[str, str]] = {
    "continue": {"en": "CONTINUE", "de": "FORTSETZEN"},
    "operations": {"en": "OPERATIONS", "de": "OPERATIONEN"},
    "terminal": {"en": "TERMINAL", "de": "TERMINAL"},
    "network": {"en": "NETWORK", "de": "NETZWERK"},
    "market": {"en": "MARKET", "de": "MARKT"},
    "loadout": {"en": "LOADOUT", "de": "AUSRÜSTUNG"},
    "inventory": {"en": "INVENTORY", "de": "INVENTAR"},
    "comms": {"en": "COMMS", "de": "KONTAKTE"},
    "profile": {"en": "PROFILE", "de": "PROFIL"},
    "achievements": {"en": "ACHIEVEMENTS", "de": "ERFOLGE"},
    "archives": {"en": "ARCHIVES", "de": "ARCHIV"},
    "settings": {"en": "SETTINGS", "de": "EINSTELLUNGEN"},
    "exit": {"en": "EXIT", "de": "BEENDEN"},
    "menu": {"en": "MENU", "de": "MENÜ"},
    "username": {"en": "OPERATOR", "de": "OPERATOR"},
    "level": {"en": "LEVEL", "de": "LEVEL"},
    "rank": {"en": "RANK", "de": "RANG"},
    "xp": {"en": "XP", "de": "XP"},
    "credits": {"en": "CREDITS", "de": "CREDITS"},
    "reputation": {"en": "REPUTATION", "de": "REPUTATION"},
    "mission_progress": {"en": "MISSION PROGRESS", "de": "MISSIONSFORTSCHRITT"},
    "trace_alert": {"en": "TRACE ALERT", "de": "TRACE-ALARM"},
    "buy": {"en": "BUY", "de": "KAUFEN"},
    "equip": {"en": "EQUIP", "de": "AUSRÜSTEN"},
    "unequip": {"en": "UNEQUIP", "de": "ABLEGEN"},
    "use": {"en": "USE", "de": "BENUTZEN"},
    "claim": {"en": "CLAIM", "de": "ABHOLEN"},
    "daily": {"en": "DAILY", "de": "TÄGLICH"},
    "weekly": {"en": "WEEKLY", "de": "WÖCHENTLICH"},
    "missions": {"en": "MISSIONS", "de": "MISSIONEN"},
    "start_mission": {"en": "START MISSION", "de": "MISSION STARTEN"},
    "abort": {"en": "ABORT", "de": "ABBRECHEN"},
    "locked": {"en": "LOCKED", "de": "GESPERRT"},
    "unlocked": {"en": "UNLOCKED", "de": "FREIGESCHALTET"},
    "owned": {"en": "OWNED", "de": "BESITZT"},
    "equipped": {"en": "EQUIPPED", "de": "AUSGERÜSTET"},
    "all": {"en": "ALL", "de": "ALLE"},
    "tools": {"en": "TOOLS", "de": "WERKZEUGE"},
    "upgrades": {"en": "UPGRADES", "de": "UPGRADES"},
    "cosmetics": {"en": "COSMETICS", "de": "KOSMETIK"},
    "access": {"en": "ACCESS", "de": "ZUGANG"},
    "intelligence": {"en": "INTELLIGENCE", "de": "INTEL"},
    "special": {"en": "SPECIAL", "de": "SPEZIAL"},
    "save_game": {"en": "SAVE GAME", "de": "SPEICHERN"},
    "load_game": {"en": "LOAD GAME", "de": "LADEN"},
    "new_operator": {"en": "NEW OPERATOR", "de": "NEUER OPERATOR"},
    "switch_operator": {"en": "SWITCH OPERATOR", "de": "OPERATOR WECHSELN"},
    "resume": {"en": "RESUME", "de": "WEITER"},
    "main_menu": {"en": "MAIN MENU", "de": "HAUPTMENÜ"},
    "quit_game": {"en": "QUIT GAME", "de": "SPIEL BEENDEN"},
    "statistics": {"en": "STATISTICS", "de": "STATISTIKEN"},
    "notifications": {"en": "NOTIFICATIONS", "de": "BENACHRICHTIGUNGEN"},
    "no_notifications": {"en": "No notifications yet.", "de": "Noch keine Benachrichtigungen."},
    "welcome": {"en": "WELCOME, OPERATOR.", "de": "WILLKOMMEN, OPERATOR."},
    "create_profile": {"en": "CREATE OPERATOR PROFILE", "de": "OPERATOR-PROFIL ERSTELLEN"},
    "initialize": {"en": "INITIALIZE", "de": "INITIALISIEREN"},
    "skip": {"en": "SKIP", "de": "ÜBERSPRINGEN"},
    "next": {"en": "NEXT", "de": "WEITER"},
    "daily_deal": {"en": "TODAY'S DEAL", "de": "ANGEBOT DES TAGES"},
    "total_bonuses": {"en": "TOTAL BONUSES", "de": "GESAMTBONI"},
    "slot_locked": {"en": "SLOT LOCKED", "de": "SLOT GESPERRT"},
    "empty": {"en": "EMPTY", "de": "LEER"},
    "chapter": {"en": "CHAPTER", "de": "KAPITEL"},
    "sim_only": {"en": "SIMULATION ONLY — all systems, IPs and networks are fictional.",
                 "de": "NUR SIMULATION — alle Systeme, IPs und Netzwerke sind fiktiv."},
    "language": {"en": "LANGUAGE", "de": "SPRACHE"},
    "theme": {"en": "THEME", "de": "DESIGN"},
}


def set_language(code: str) -> None:
    global _LANG
    _LANG = code if code in ("en", "de") else "en"


def language() -> str:
    return _LANG


def tr(key: str) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key.upper()
    return entry.get(_LANG) or entry["en"]
