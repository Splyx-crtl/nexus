"""Game key activation that keeps working offline.

The key is checked once by the server (``POST /license/activate``), which answers with a signed licence: key id, this computer's id and an
expiry date. The game verifies the signature with the public key built into it, so the game can be played offline until the licence
expires (30 days; every start-up with a connection renews it silently). Editing the settings file does not help: a licence the server
did not sign, or one made for another computer, does not verify. Deactivating or deleting a key stops the game at its next renewal.

No network code here (that lives in online.py); this module only stores and verifies."""
from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from dataclasses import dataclass

from . import ed25519
from .config import FROZEN
from .version import LICENSE_PUBLIC_KEY


def public_key_hex() -> str:
    """The key licences must verify with. Source runs (development, tests) may override or switch it off with NEXUS_LICENSE_PUBKEY
    (empty = no key needed); a packaged game ignores the environment, so setting a variable cannot turn the check off."""
    key = LICENSE_PUBLIC_KEY
    if not FROZEN and "NEXUS_LICENSE_PUBKEY" in os.environ:
        key = os.environ["NEXUS_LICENSE_PUBKEY"]
    key = (key or "").strip().lower()
    return key if re.fullmatch(r"[0-9a-f]{64}", key) else ""


def enabled() -> bool:
    """Builds without a public key (development, tests) need no key to play."""
    return bool(public_key_hex())


def device_id(settings) -> str:
    """A random id of this installation, created once. It is what the server binds a key to."""
    current = settings.get("device_id") or ""
    if not re.fullmatch(r"[0-9a-f]{32}", current):
        current = uuid.uuid4().hex
        settings.set("device_id", current)
    return current


@dataclass
class Status:
    ok: bool
    reason: str = ""            # "none" (never activated) | "bad" | "device" | "expired" | "" when ok
    expires: int = 0
    message: str = ""

    @property
    def days_left(self) -> int:
        return max(0, int((self.expires - time.time()) // 86400))


MESSAGES = {
    "none": "Enter your game key to activate NEXUS.",
    "bad": "The stored licence is not valid. Enter your game key again.",
    "device": "This licence belongs to another computer. Enter your game key again.",
    "expired": "Your licence has run out. Connect to the internet once to renew it.",
}


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def read_token(token: str, public_hex: str) -> dict | None:
    """The licence payload if the signature is genuine, else None."""
    try:
        payload_b64, signature_b64 = token.split(".")
        payload = _unb64(payload_b64)
        if not ed25519.verify(bytes.fromhex(public_hex), payload, _unb64(signature_b64)):
            return None
        data = json.loads(payload)
        return data if isinstance(data, dict) and data.get("v") == 1 else None
    except (ValueError, TypeError, KeyError):
        return None


def check(settings, now: float | None = None) -> Status:
    """Is this installation licensed right now? Works without a connection."""
    public = public_key_hex()
    if not public:
        return Status(True)
    token = settings.get("license_token") or ""
    if not token:
        return Status(False, "none", message=MESSAGES["none"])
    data = read_token(token, public)
    if data is None:
        return Status(False, "bad", message=MESSAGES["bad"])
    if data.get("dev") != device_id(settings):
        return Status(False, "device", message=MESSAGES["device"])
    expires = int(data.get("exp", 0))
    if expires < (now if now is not None else time.time()):
        return Status(False, "expired", expires, MESSAGES["expired"])
    return Status(True, "", expires)


def store(settings, token: str, key: str) -> Status:
    """Keep a freshly issued licence (and the key, for silent renewals). Refuses anything that does not verify."""
    data = read_token(token, public_key_hex()) if public_key_hex() else None
    if data is None or data.get("dev") != device_id(settings):
        return Status(False, "bad", message=MESSAGES["bad"])
    settings.set("license_token", token)
    settings.set("license_key", key.strip())
    settings.set("online_key", key.strip())                  # the online login uses the same key
    return check(settings)


def clear(settings) -> None:
    settings.set("license_token", "")
