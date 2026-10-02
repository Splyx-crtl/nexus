"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-III are complete (levels 1-70). Act IV
(71-95) is skipped for now — it needs B5 (crypto commands), not yet built — and Act V (96-120) is in progress instead
(Chapter 1 of 3), since it only needs B6 (PowerShell/cmd), which is done. act5_m96 currently lists act3_m70 as its
prerequisite; once Act IV exists, that should point at its own closing milestone instead. The story bible
(docs/story/) is approved, but most acts are still to be written."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act5 import ACT5

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT5]
