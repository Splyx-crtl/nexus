"""Creates the key pair that signs the game licences.

    python tools/make_license_key.py

* The SECRET seed is written to  license_seed.txt  in the project folder (git-ignored). Put its content into the server's environment as
  NEXUS_LICENSE_SEED (Railway -> Variables) and keep a backup somewhere safe. Never commit it, never paste it into a chat.
* The PUBLIC key is written into nexus/version.py (LICENSE_PUBLIC_KEY). It is not secret; it is built into the game so the game can verify
  licences offline.

Run it once. If license_seed.txt already exists it is reused (so the public key stays the same). If you lose the seed, make a new pair:
every player then has to activate again."""
from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nexus import ed25519  # noqa: E402


def main() -> int:
    seed_file = ROOT / "license_seed.txt"
    if seed_file.exists():
        seed = bytes.fromhex(seed_file.read_text().strip())
        print("Using the existing license_seed.txt.")
    else:
        seed = secrets.token_bytes(32)
        seed_file.write_text(seed.hex() + "\n")
        print("Created license_seed.txt (SECRET - copy its content to the server variable NEXUS_LICENSE_SEED).")
    public = ed25519.public_key(seed).hex()
    version = ROOT / "nexus" / "version.py"
    text = version.read_text(encoding="utf-8")
    new, count = re.subn(r'^LICENSE_PUBLIC_KEY = ".*"$', f'LICENSE_PUBLIC_KEY = "{public}"', text, flags=re.M)
    if count != 1:
        print("Could not find LICENSE_PUBLIC_KEY in nexus/version.py.")
        return 1
    version.write_text(new, encoding="utf-8")
    print(f"Public key written to nexus/version.py:\n  {public}")
    print("\nNext: set NEXUS_LICENSE_SEED on the server, release the new game version. Then every player must activate with a key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
