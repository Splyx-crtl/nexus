"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-V are complete: levels 1-120 are
fully contiguous (act4_m95, the Act IV finale, is act5_m96's prerequisite). Act VI is in progress (Chapters 1-2 of 3,
levels 121-137), now that B8 (PowerShell/cmd scripting) exists. The story bible (docs/story/) is approved, but Acts
VII-IX (levels 146-200) are still to be written, and some need further engine work first — see
docs/3.0-PROGRESS.md's B-section checklist (B10 GUI tool windows, a new "defender" mission shape for Act VII)."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act4 import ACT4
from .act5 import ACT5
from .act6 import ACT6

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT4, *ACT5, *ACT6]
