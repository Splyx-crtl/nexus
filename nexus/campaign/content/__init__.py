"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-III and V are complete (levels 1-70,
96-120). Act IV (71-95) is in progress (Chapter 1 of 3) — B5 (crypto commands) now exists, so it's no longer blocked.
act5_m96 currently lists act3_m70 as its prerequisite (a placeholder from when Act IV was skipped); once Act IV's own
closing milestone (act4_m95) exists, that should point there instead. The story bible (docs/story/) is approved, but
Acts VI-IX are still to be written."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act4 import ACT4
from .act5 import ACT5

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT4, *ACT5]
