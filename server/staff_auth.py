"""F3: staff accounts (roles, TOTP, invite codes) - pure helpers, no FastAPI or DB, so they're easy to test in
isolation. Password hashing and TOTP verification are the two places a subtle bug would actually matter, so they
live here on their own rather than inline in server/app.py.

Role hierarchy (docs/3.0-PROGRESS.md F3, "Developer > Owner > Moderator > Helper"): a numeric rank per role, so
"can this role do X" is just a >= comparison. "developer" is deliberately never granted through an invite code -
only the one-time bootstrap (server/app.py's /admin/staff/bootstrap, itself gated behind the existing legacy
ADMIN_TOKEN/ADMIN_USER+PASSWORD) can create one, so a compromised Owner account can escalate at most to Owner,
never to Developer.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

ROLES = ("helper", "moderator", "owner", "developer")
ROLE_RANK = {role: i for i, role in enumerate(ROLES)}
INVITABLE_ROLES = ("helper", "moderator", "owner")     # developer is bootstrap-only, never invited

PBKDF2_ITERATIONS = 310_000


def role_rank(role: str) -> int:
    return ROLE_RANK.get(role, -1)


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with a random salt, stdlib only (no new dependency for something this security-sensitive
    just to save a few lines). Format: 'pbkdf2$<iterations>$<salt_hex>$<hash_hex>'."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def new_totp_secret() -> str:
    """A 20-byte (160-bit) base32 secret, the standard size for TOTP (RFC 6238 / Google Authenticator)."""
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def totp_at(secret: str, counter: int, digits: int = 6) -> str:
    """RFC 6238 TOTP over RFC 4226 HOTP: stdlib hmac/hashlib only, no pyotp dependency for six lines of math."""
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    msg = counter.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, now: float, window: int = 1, step: int = 30) -> bool:
    """Accepts a code from the current 30s step or ``window`` steps on either side (clock drift tolerance)."""
    code = code.strip()
    if not code.isdigit():
        return False
    counter = int(now // step)
    return any(hmac.compare_digest(code.zfill(6), totp_at(secret, counter + offset)) for offset in range(-window, window + 1))


def provisioning_uri(secret: str, username: str, issuer: str = "NEXUS") -> str:
    """otpauth:// URI an authenticator app (or a QR code built from it) can consume directly."""
    import urllib.parse
    label = urllib.parse.quote(f"{issuer}:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={urllib.parse.quote(issuer)}&algorithm=SHA1&digits=6&period=30"
