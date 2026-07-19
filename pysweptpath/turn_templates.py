"""Standard 90° and 180° turn templates for swept-path profiles."""

from __future__ import annotations

import math
from typing import Any

from .envelope import swept_envelope_polygon
from .kinematics import densify_path
from .path_follow import follow_path
from .vehicle import Vehicle


def turn_arc_center(radius_m: float, turn_left: bool = True) -> tuple[float, float]:
    """Arc centre for template turns (same geometry as path builders)."""
    r = max(1.0, float(radius_m))
    sign = 1.0 if turn_left else -1.0
    return (0.0, sign * r)


def make_90_degree_path(
    radius_m: float,
    approach_m: float = 25.0,
    exit_m: float = 25.0,
    step_m: float = 0.5,
    turn_left: bool = True,
) -> list[tuple[float, float]]:
    """
    Straight approach → quarter-circle of radius R → straight exit.

    Path centreline: approach along +X, turns 90° (left = +Y exit).
    Arc centre: turn_arc_center(R).
    """
    r = max(1.0, float(radius_m))
    pts: list[tuple[float, float]] = []
    n_app = max(2, int(math.ceil(approach_m / step_m)))
    for i in range(n_app + 1):
        t = i / n_app
        pts.append((-approach_m + t * approach_m, 0.0))
    sign = 1.0 if turn_left else -1.0
    n_arc = max(8, int(math.ceil((math.pi / 2) * r / step_m)))
    for i in range(1, n_arc + 1):
        th = (math.pi / 2) * (i / n_arc)
        x = 0.0 + r * math.sin(th)
        y = sign * r + (-sign) * r * math.cos(th)
        pts.append((x, y))
    end = pts[-1]
    n_ex = max(2, int(math.ceil(exit_m / step_m)))
    for i in range(1, n_ex + 1):
        t = i / n_ex
        pts.append((end[0], end[1] + sign * t * exit_m))
    return pts


def make_180_degree_path(
    radius_m: float,
    approach_m: float = 25.0,
    exit_m: float = 25.0,
    step_m: float = 0.5,
    turn_left: bool = True,
) -> list[tuple[float, float]]:
    """
    Straight approach → semicircle of radius R → straight exit opposite direction.

    U-turn: approach along +X, exit parallel -X offset by 2R.
    Arc centre: turn_arc_center(R).
    """
    r = max(1.0, float(radius_m))
    pts: list[tuple[float, float]] = []
    n_app = max(2, int(math.ceil(approach_m / step_m)))
    for i in range(n_app + 1):
        t = i / n_app
        pts.append((-approach_m + t * approach_m, 0.0))
    sign = 1.0 if turn_left else -1.0
    n_arc = max(12, int(math.ceil(math.pi * r / step_m)))
    for i in range(1, n_arc + 1):
        th = math.pi * (i / n_arc)
        x = 0.0 + r * math.sin(th)
        y = sign * r + (-sign) * r * math.cos(th)
        pts.append((x, y))
    end = pts[-1]
    n_ex = max(2, int(math.ceil(exit_m / step_m)))
    for i in range(1, n_ex + 1):
        t = i / n_ex
        pts.append((end[0] - t * exit_m, end[1]))
    return pts


def _point_in_turn_sector(
    x: float,
    y: float,
    cx: float,
    cy: float,
    turn_deg: int,
    turn_left: bool,
    margin_rad: float = 0.12,
) -> bool:
    """True if (x,y) lies in the template arc angular sector about the turn centre."""
    dx = x - cx
    dy = y - cy
    # Parametric path uses relative (r*sin θ, -sign*r*cos θ), θ∈[0, α]
    # Map to θ via atan2 so θ=0 is start of arc.
    sign = 1.0 if turn_left else -1.0
    # relative = (r sin θ, -sign r cos θ) → sin θ = dx/r, cos θ = -sign*dy/r
    # θ = atan2(dx, -sign*dy) for left: atan2(dx, -dy)
    th = math.atan2(dx, -sign * dy)
    if th < -1e-6:
        th += 2 * math.pi
    alpha = math.pi / 2 if turn_deg == 90 else math.pi
    return -margin_rad <= th <= alpha + margin_rad


def fitting_turn_radii(
    envelope: list[list[float]] | list[tuple[float, float]] | None,
    center: tuple[float, float],
    path_radius_m: float,
    turn_deg: int,
    turn_left: bool = True,
) -> dict[str, float | list[float] | None]:
    """
    Inscribed (inner) and exscribed (outer) circles about the turn centre.

    Radii are min/max distance from the turn centre to swept-envelope vertices
    that lie in the turn arc sector (approach/exit straights excluded).
    """
    cx, cy = center
    r_path = float(path_radius_m)
    r_in = r_path
    r_out = r_path
    n_used = 0
    if envelope:
        dists: list[float] = []
        for p in envelope:
            x, y = float(p[0]), float(p[1])
            if not _point_in_turn_sector(x, y, cx, cy, turn_deg, turn_left):
                continue
            d = math.hypot(x - cx, y - cy)
            if d > 0.05:
                dists.append(d)
        if dists:
            r_in = min(dists)
            r_out = max(dists)
            n_used = len(dists)
    return {
        "center": [cx, cy],
        "path_radius_m": r_path,
        "inscribed_radius_m": float(r_in),
        "exscribed_radius_m": float(r_out),
        "sector_samples": n_used,
    }


def _wheelbase_m(vehicle: Vehicle) -> float:
    arts = getattr(vehicle, "articulation_positions_m", None) or (
        [vehicle.articulation_longitudinal_m]
        if getattr(vehicle, "articulation_longitudinal_m", None) is not None
        else []
    )
    if arts:
        return max(0.1, 0.0 - arts[0])
    rear_pos = min((a.longitudinal_pos for a in vehicle.axles), default=-4.0)
    return max(0.1, 0.0 - rear_pos)


def _max_steer_deg(vehicle: Vehicle, fallback: float = 42.0) -> float:
    m = fallback
    for a in vehicle.axles:
        if a.is_steering and a.max_steer_angle_deg is not None:
            m = min(m, a.max_steer_angle_deg)
    return m


def simulate_turn_profile(
    vehicle: Vehicle,
    *,
    turn_deg: int,
    radius_m: float,
    approach_m: float = 25.0,
    exit_m: float = 25.0,
    step_m: float = 0.35,
    stop_lock: bool = True,
    design_speed_kmh: float = 5.0,
    turn_left: bool = True,
) -> dict[str, Any]:
    """Run path-follow on a template turn; return path, envelope, metrics."""
    if turn_deg == 180:
        path = make_180_degree_path(
            radius_m, approach_m, exit_m, step_m=min(step_m, 0.5), turn_left=turn_left
        )
    else:
        path = make_90_degree_path(
            radius_m, approach_m, exit_m, step_m=min(step_m, 0.5), turn_left=turn_left
        )

    densified = densify_path(path, max(0.15, step_m * 0.5)).tolist()
    densified = [(float(p[0]), float(p[1])) for p in densified]
    wb = _wheelbase_m(vehicle)
    max_steer = _max_steer_deg(vehicle)
    speed = design_speed_kmh / 3.6
    lookahead = max(3.0, 2.0 * step_m)

    positions, steer_hist, segment_poses = follow_path(
        densified,
        wheelbase_m=wb,
        step_m=step_m,
        lookahead_m=lookahead,
        max_steer_deg=max_steer,
        stop_lock_enabled=stop_lock,
        rate_of_turn_deg_per_s=15.0,
        speed_m_per_s=speed,
        pid_enabled=False,
        path_recovery_gain=0.8,
        vehicle=vehicle,
    )

    max_steer_achieved = max((abs(s) for s in steer_hist), default=0.0)
    min_radius = (
        wb / math.tan(math.radians(max_steer_achieved))
        if max_steer_achieved > 1e-6
        else 0.0
    )
    env = swept_envelope_polygon(positions, vehicle, segment_poses=segment_poses)
    envelope: list[list[float]] | None = None
    if env is not None and not getattr(env, "is_empty", True):
        geom = env
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        if hasattr(geom, "exterior"):
            envelope = [[float(x), float(y)] for x, y in geom.exterior.coords]

    center = turn_arc_center(radius_m, turn_left=turn_left)
    fit = fitting_turn_radii(
        envelope, center, radius_m, turn_deg=turn_deg, turn_left=turn_left
    )

    # Downsample positions for JSON
    pos_list = list(positions) if positions else []
    if len(pos_list) > 250:
        step = max(1, len(pos_list) // 250)
        pos_list = pos_list[::step] + (
            [pos_list[-1]] if pos_list[-1] != pos_list[::step][-1] else []
        )

    return {
        "turn_deg": turn_deg,
        "radius_m": radius_m,
        "path": densified
        if len(densified) <= 400
        else densified[:: max(1, len(densified) // 400)],
        "envelope": envelope,
        "positions_sample": [
            [float(p[0]), float(p[1]), float(p[2])] for p in pos_list
        ],
        "max_steer_deg": max_steer_achieved,
        "min_radius_m": min_radius,
        "wheelbase_m": wb,
        "steer_limit_deg": max_steer,
        "steps": len(positions) if positions else 0,
        "saturated": max_steer_achieved >= max_steer - 0.5,
        "turn_center": list(center),
        "inscribed_radius_m": fit["inscribed_radius_m"],
        "exscribed_radius_m": fit["exscribed_radius_m"],
        "path_radius_m": fit["path_radius_m"],
        "fit_sector_samples": fit["sector_samples"],
    }


def simulate_standard_profiles(
    vehicle: Vehicle,
    *,
    radius_90_m: float = 12.5,
    radius_180_m: float = 12.5,
    step_m: float = 0.35,
    stop_lock: bool = True,
) -> dict[str, Any]:
    """Generate both 90° and 180° turn profiles for a vehicle."""
    t90 = simulate_turn_profile(
        vehicle,
        turn_deg=90,
        radius_m=radius_90_m,
        step_m=step_m,
        stop_lock=stop_lock,
    )
    t180 = simulate_turn_profile(
        vehicle,
        turn_deg=180,
        radius_m=radius_180_m,
        step_m=step_m,
        stop_lock=stop_lock,
    )
    return {
        "vehicle_name": vehicle.name,
        "profiles": {"90": t90, "180": t180},
    }
