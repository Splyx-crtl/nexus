"""NEXUS 3.0 shell engine: a simulated Linux (bash) and Windows (PowerShell / cmd) world.

Pure Python without Qt, so everything here can be tested headless. Nothing in this package touches the real file system or the network:
every machine, file, user and service is data inside the game.

Modules: fs (virtual file system), parser/interp (shell languages), commands (the command library), machine (hosts and sessions).
"""
