"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Only Act I exists so far — a proof that the
v3 format, validator, runner and solver bot all work end to end; the story bible (docs/story/) is approved, but the other
eight acts are still to be written, and several need engine work first (02-acts-and-levels.md's table)."""
from .act1 import ACT1

ALL_MISSIONS = [*ACT1]
