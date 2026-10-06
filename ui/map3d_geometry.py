"""D2: pure math for the 3D network map (ui/network_map_3d.qml) - deterministic node depth, and the per-link
midpoint/length/quaternion needed to align a unit cylinder (Qt Quick 3D's "#Cylinder" primitive: 1 unit tall,
centered at the origin, long axis +Y) between two arbitrary points. Kept Qt-free and unit-testable; the QML scene
only binds these precomputed numbers, it does no vector math of its own.
"""
from __future__ import annotations

import hashlib
import math

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]       # (w, x, y, z)


def node_depth(server_id: str) -> float:
    """A deterministic pseudo-random z in [-1, 1] from the server's own id - the same id always gets the same
    depth (the map doesn't jitter between refreshes), but different servers spread out in 3D instead of sitting
    on a flat plane."""
    h = hashlib.sha256(server_id.encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1


def node_position(x2d: float, y2d: float, server_id: str, spread: float = 6.0, depth_scale: float = 2.5) -> Vec3:
    """Map the existing 2D layout (0..1, 0..1, see ui/map_view.py's NetworkMapWidget._pos) plus a deterministic
    depth into a 3D scene position, centered on the origin."""
    return ((x2d - 0.5) * spread, (0.5 - y2d) * spread, node_depth(server_id) * depth_scale)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _length(v: Vec3) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _normalize(v: Vec3) -> Vec3:
    n = _length(v)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-9 else (0.0, 1.0, 0.0)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rotate_vector(q: Quat, v: Vec3) -> Vec3:
    """Rotate ``v`` by quaternion ``q`` - used here only by tests, to verify link_geometry's quaternion actually
    points a +Y axis the right way, but kept as a real (not test-only) function since it's genuinely reusable."""
    w, x, y, z = q
    qv = (x, y, z)
    t = tuple(2 * c for c in _cross(qv, v))
    cross2 = _cross(qv, t)
    return (v[0] + w * t[0] + cross2[0], v[1] + w * t[1] + cross2[1], v[2] + w * t[2] + cross2[2])


def link_geometry(a: Vec3, b: Vec3) -> dict:
    """Midpoint, length and the quaternion (w, x, y, z) that rotates a unit +Y cylinder to point from a to b."""
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    length = _length(_sub(b, a))
    direction = _normalize(_sub(b, a))
    up = (0.0, 1.0, 0.0)
    dot = max(-1.0, min(1.0, _dot(up, direction)))
    if dot > 1 - 1e-9:                      # already pointing straight up: identity rotation
        quat: Quat = (1.0, 0.0, 0.0, 0.0)
    elif dot < -1 + 1e-9:                   # pointing straight down: flip 180 degrees around any perpendicular axis
        quat = (0.0, 1.0, 0.0, 0.0)
    else:
        axis = _normalize(_cross(up, direction))
        angle = math.acos(dot)
        s = math.sin(angle / 2)
        quat = (math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s)
    return {"mid": mid, "length": length, "quat": quat}
