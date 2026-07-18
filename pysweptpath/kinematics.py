"""Incremental bicycle model + Ackermann angles. See PDR §2–3."""

import logging
from dataclasses import dataclass

import numpy as np

from .vehicle import Vehicle

logger = logging.getLogger(__name__)


@dataclass
class PathPoint:
    x: float
    y: float
    heading_rad: float  # tangent direction
    curvature: float    # 1/radius, positive = left


def densify_path(points: list[tuple[float, float]], max_segment_m: float) -> np.ndarray:
    """Densify polyline so no segment exceeds max_segment_m."""
    pts = np.array(points, dtype=float)
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        d = np.hypot(b[0] - a[0], b[1] - a[1])
        if d <= max_segment_m:
            out.append(b)
            continue
        n = int(np.ceil(d / max_segment_m))
        for k in range(1, n + 1):
            t = k / n
            out.append((1 - t) * a + t * b)
    return np.array(out)


def path_headings_curvature(pts: np.ndarray) -> list[PathPoint]:
    """Compute heading and curvature along path. pts shape (N,2)."""
    if len(pts) < 2:
        return [PathPoint(pts[0, 0], pts[0, 1], 0.0, 0.0)] if len(pts) else []
    out = []
    for i in range(len(pts)):
        x, y = pts[i, 0], pts[i, 1]
        if i == 0:
            dx = pts[1, 0] - x
            dy = pts[1, 1] - y
        elif i == len(pts) - 1:
            dx = x - pts[i - 1, 0]
            dy = y - pts[i - 1, 1]
        else:
            dx = pts[i + 1, 0] - pts[i - 1, 0]
            dy = pts[i + 1, 1] - pts[i - 1, 1]
        heading = np.arctan2(dy, dx)
        # curvature from adjacent segments
        if i > 0 and i < len(pts) - 1:
            ax, ay = pts[i, 0] - pts[i - 1, 0], pts[i, 1] - pts[i - 1, 1]
            bx, by = pts[i + 1, 0] - pts[i, 0], pts[i + 1, 1] - pts[i, 1]
            la, lb = np.hypot(ax, ay), np.hypot(bx, by)
            if la > 1e-9 and lb > 1e-9:
                cross = ax * by - ay * bx
                curvature = 2 * cross / (la * lb + 1e-12)
            else:
                curvature = 0.0
        else:
            curvature = 0.0
        out.append(PathPoint(x, y, heading, curvature))
    return out


def ackermann_steer_angle(wheelbase: float, curvature: float) -> float:
    """Steer angle (rad) for bicycle model: tan(steer) = wheelbase * curvature."""
    if abs(curvature) < 1e-12:
        return 0.0
    return np.arctan(wheelbase * curvature)


def simulate_path(vehicle: Vehicle, path_points: list[PathPoint], step_indices: list[int],
                  max_steer_deg: float | None) -> list[tuple[float, float, float]]:
    """
    Incremental simulation along path. Returns list of (x, y, heading_rad) for steering axle.
    Stops and warns if steer exceeds max_steer_deg.
    """
    wb = 0.0
    if len(vehicle.axles) >= 2:
        pos = [a.longitudinal_pos for a in vehicle.axles]
        wb = abs(max(pos) - min(pos))
    if wb < 1e-9:
        logger.warning("Vehicle wheelbase near zero")
    results = []
    for idx in step_indices:
        if idx >= len(path_points):
            break
        pt = path_points[idx]
        steer_rad = ackermann_steer_angle(wb, pt.curvature)
        steer_deg = np.degrees(steer_rad)
        if max_steer_deg is not None and abs(steer_deg) > max_steer_deg:
            logger.warning("Steer angle %.2f deg exceeds limit %.2f at index %d", steer_deg, max_steer_deg, idx)
        results.append((pt.x, pt.y, pt.heading_rad))
    return results
