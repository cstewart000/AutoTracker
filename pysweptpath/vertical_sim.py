"""Vertical profile mode: chainage (x) vs elevation (y), rigid axles, chord–terrain clearance."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

from .vehicle import Vehicle, VerticalProfile

logger = logging.getLogger(__name__)


@dataclass
class VerticalFrame:
    s_ref: float
    axle_s: list[float]
    z_ground: list[float]
    z_wheel_center: list[float]


def ground_tangent_unit(s: float, path: np.ndarray) -> tuple[float, float]:
    """Unit tangent (ds, dz) along piecewise-linear ground at chainage s."""
    if len(path) < 2:
        return (1.0, 0.0)
    xs = path[:, 0]
    zz = path[:, 1]
    if s <= xs[0]:
        i = 0
    elif s >= xs[-1]:
        i = len(path) - 2
    else:
        i = int(np.searchsorted(xs, s, side="right")) - 1
        i = max(0, min(i, len(path) - 2))
    ds = float(xs[i + 1] - xs[i])
    dz = float(zz[i + 1] - zz[i])
    L = float(np.hypot(ds, dz))
    if L < 1e-12:
        return (1.0, 0.0)
    return (ds / L, dz / L)


def ground_tangent_secant(
    s: float, path: np.ndarray, half_width_m: float,
) -> tuple[float, float]:
    """
    Unit tangent from secant over [s-half, s+half] on the profile (interp_z).
    Smooths pitch on piecewise-linear alignments — trailer pitch changes gradually instead of snapping
    at vertices. Only used for trailer body orientation (central axle); other axles are not used for this.
    """
    if len(path) < 2 or half_width_m <= 0:
        return ground_tangent_unit(s, path)
    s_min, s_max = float(path[0, 0]), float(path[-1, 0])
    s_lo = max(s_min, s - half_width_m)
    s_hi = min(s_max, s + half_width_m)
    if s_hi <= s_lo + 1e-9:
        return ground_tangent_unit(s, path)
    z_lo = interp_z(s_lo, path)
    z_hi = interp_z(s_hi, path)
    ds = s_hi - s_lo
    dz = z_hi - z_lo
    L = math.hypot(ds, dz)
    if L < 1e-12:
        return (1.0, 0.0)
    return (ds / L, dz / L)


def interp_z(s: float, path: np.ndarray) -> float:
    """Piecewise linear z(s); path columns (chainage, elevation)."""
    if len(path) < 2:
        return float(path[0, 1]) if len(path) else 0.0
    xs = path[:, 0]
    if s <= xs[0]:
        return float(path[0, 1])
    if s >= xs[-1]:
        return float(path[-1, 1])
    i = int(np.searchsorted(xs, s, side="right")) - 1
    i = max(0, min(i, len(path) - 2))
    s0, z0 = path[i, 0], path[i, 1]
    s1, z1 = path[i + 1, 0], path[i + 1, 1]
    t = (s - s0) / (s1 - s0 + 1e-15)
    return float(z0 + t * (z1 - z0))


def chord_ground_margin(path: np.ndarray, sa: float, sb: float, za: float, zb: float, n: int = 40) -> float:
    """Min over [sa,sb] of (chord_z - z_ground(s)); negative = rigid chord below terrain."""
    if sb < sa:
        sa, sb = sb, sa
        za, zb = zb, za
    margin = 1e9
    for t in np.linspace(sa, sb, n):
        zg = interp_z(float(t), path)
        zc = za + (zb - za) * (t - sa) / (sb - sa + 1e-15)
        margin = min(margin, zc - zg)
    return float(margin)


def min_margin_all_spans(path: np.ndarray, axle_s: list[float], zg: list[float]) -> float:
    """Sorted by chainage: min chord–terrain margin between consecutive axles."""
    pairs = sorted(zip(axle_s, zg), key=lambda p: p[0])
    m = 1e9
    for i in range(len(pairs) - 1):
        (sa, za), (sb, zb) = pairs[i], pairs[i + 1]
        if abs(sb - sa) < 1e-6:
            continue
        m = min(m, chord_ground_margin(path, sa, sb, za, zb))
    return float(m)


def simulate_vertical(
    path: np.ndarray,
    vehicle: Vehicle,
    vp: VerticalProfile,
    step_m: float,
) -> tuple[list[VerticalFrame], float, bool]:
    """
    Move steering axle along chainage; all axles follow profile. Returns frames, global min margin, pass clearance.
    path: (N,2) chainage, elevation.
    """
    path = np.asarray(path, dtype=float)
    path = path[path[:, 0].argsort()]
    min_pos = min(a.longitudinal_pos for a in vehicle.axles)
    max_pos = max(a.longitudinal_pos for a in vehicle.axles)
    s_lo, s_hi = float(path[0, 0]), float(path[-1, 0])
    # Steering at s; need s + min_pos >= s_lo and s + max_pos <= s_hi
    s_start = s_lo - min_pos + 1e-3
    s_end = s_hi - max_pos - 1e-3
    if s_end <= s_start:
        logger.warning("Vertical profile: path too short for vehicle wheelbase; using single step")
        s_end = s_start + step_m
    n = max(2, int(np.ceil((s_end - s_start) / step_m)) + 1)
    ss = np.linspace(s_start, s_end, n)
    frames: list[VerticalFrame] = []
    global_min = 1e9
    R = vp.wheel_radius_m
    for s_ref in ss:
        axle_s = [s_ref + a.longitudinal_pos for a in vehicle.axles]
        z_ground = [interp_z(s, path) for s in axle_s]
        z_wc = [z + R for z in z_ground]
        mm = min_margin_all_spans(path, axle_s, z_ground)
        global_min = min(global_min, mm)
        frames.append(VerticalFrame(s_ref=float(s_ref), axle_s=axle_s, z_ground=z_ground, z_wheel_center=z_wc))
    ok = global_min >= vp.ground_clearance_m - 1e-6
    logger.info("Vertical: min chord–terrain margin %.3f m (required %.3f m)", global_min, vp.ground_clearance_m)
    return frames, global_min, ok
