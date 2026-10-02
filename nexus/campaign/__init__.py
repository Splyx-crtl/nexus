"""NEXUS 3.0 campaign framework: the v3 mission format, its validator, an event-driven runner that tracks a mission's
objectives against the shell engine in real time, world-building scenarios, generators for procedural Mini missions, and
a solver bot that proves every authored mission is actually completable.

Separate from the 2.x mission system (`nexus/mission_engine.py`), which keeps running the shipped campaign unchanged.
See `docs/3.0-PROGRESS.md` category C and `docs/story/` for the design this package implements.
"""
