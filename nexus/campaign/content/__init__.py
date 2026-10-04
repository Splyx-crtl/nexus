"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-V are complete: levels 1-120 are
fully contiguous (act4_m95, the Act IV finale, is act5_m96's prerequisite). Acts VI-VII are complete (levels
121-165); act7.py's module docstring explains how Act VII catches up a continuity gap found between Acts V-VI and
the approved story bible. Act VIII is complete (levels 166-185) and uses F2's "Endless Ops" procedural generator
(nexus/campaign/endless.py) for its contract-queue missions; act8.py's module docstring flags a second, smaller
continuity gap (the decisions 2-4/6 content vs. docs/story/03-endings.md's consequence map) left for the user to
review. The story bible (docs/story/) is approved, but Act IX (levels 186-200, the finale) is still to be written —
see docs/3.0-PROGRESS.md's B-section checklist (B10 GUI tool windows) and C5 (ending mechanics, still unbuilt)."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act4 import ACT4
from .act5 import ACT5
from .act6 import ACT6
from .act7 import ACT7
from .act8 import ACT8

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT4, *ACT5, *ACT6, *ACT7, *ACT8]
