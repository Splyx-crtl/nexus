"""Mission-content translation blocks: one module per act (per docs/3.0-PROGRESS.md's "translate blockweise" plan),
each registering its missions into nexus/campaign/i18n.py's TRANSLATIONS table on import. Importing this package is
enough to load every translated block that exists so far; ui/campaign_window.py does this once at startup.
"""
from . import de_act1  # noqa: F401
from . import de_act2  # noqa: F401
from . import de_act3  # noqa: F401
