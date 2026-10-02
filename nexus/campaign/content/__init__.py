"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-II are complete; Act III is in
progress (Chapter 1 of 3). The story bible (docs/story/) is approved, but most acts are still to be written, and
several need engine work first (02-acts-and-levels.md's table)."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3]
