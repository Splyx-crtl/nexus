"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-V are complete: levels 1-120 are
fully contiguous (act4_m95, the Act IV finale, is act5_m96's prerequisite). Act VI is complete (levels 121-145). Act
VII is in progress (Chapter 1 of 2, levels 146-155) — the role-reversal "defender" act; see act7.py's module
docstring for how it catches up a continuity gap found between Acts V-VI and the approved story bible. The story
bible (docs/story/) is approved, but Acts VIII-IX (levels 166-200) are still to be written, and need further engine
work first — see docs/3.0-PROGRESS.md's B-section checklist (B10 GUI tool windows, F2 endless-ops)."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act4 import ACT4
from .act5 import ACT5
from .act6 import ACT6
from .act7 import ACT7

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT4, *ACT5, *ACT6, *ACT7]
