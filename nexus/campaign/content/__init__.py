"""Hand-authored mission content, act by act (C4 in docs/3.0-PROGRESS.md). Acts I-V are complete: levels 1-120 are
fully contiguous (act4_m95, the Act IV finale, is act5_m96's prerequisite). Acts VI-VIII are complete (levels
121-185); act7.py's module docstring explains how Act VII catches up a continuity gap found between Acts V-VI and
the approved story bible, and act8.py's flags a second, smaller one (decisions 2-4/6 vs.
docs/story/03-endings.md's consequence map) left for the user to review. **Act IX (levels 186-200) is complete — the
full 200-level campaign is written.** It delivers the finale and the ending choice (decision:8); see act9.py's
module docstring for the honest scope note on nexus/campaign/endings.py (C5's first real version: a tested data/
logic layer for which endings are reachable, not yet wired into live play, since the v3 save/profile schema,
docs/3.0-PROGRESS.md §A2, is still unbuilt). Remaining work is everything outside C4: C5's live wiring, C6 (modes/
hints/lexicon), C7 (post-200 free replay), German translation, and the D-G categories (UI/3D, audio, online/team
panel, release)."""
from .act1 import ACT1
from .act2 import ACT2
from .act3 import ACT3
from .act4 import ACT4
from .act5 import ACT5
from .act6 import ACT6
from .act7 import ACT7
from .act8 import ACT8
from .act9 import ACT9

ALL_MISSIONS = [*ACT1, *ACT2, *ACT3, *ACT4, *ACT5, *ACT6, *ACT7, *ACT8, *ACT9]
