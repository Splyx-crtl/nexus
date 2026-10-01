"""Writes build/version_info.txt (Windows file-version resource for the EXE) from nexus/version.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
text = (ROOT / "nexus" / "version.py").read_text(encoding="utf-8")
version = re.search(r'VERSION\s*=\s*"([^"]+)"', text).group(1)
parts = (version.split(".") + ["0", "0", "0"])[:4]
tup = ", ".join(parts)
content = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Toto'),
      StringStruct('FileDescription', 'NEXUS // TERMINAL - Tactical Cyber Operations Simulator'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'NEXUS'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Toto - MIT License'),
      StringStruct('OriginalFilename', 'NEXUS.exe'),
      StringStruct('ProductName', 'NEXUS // TERMINAL'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
out = ROOT / "build"
out.mkdir(exist_ok=True)
(out / "version_info.txt").write_text(content, encoding="utf-8")
print(f"version_info.txt written for {version}")
