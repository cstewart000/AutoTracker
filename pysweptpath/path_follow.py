"""Follow a target polyline with steering saturation (pure pursuit + PID).

If the path is too tight for the vehicle max steer, the controller saturates
and the vehicle continues on max curvature while attempting to re-acquire.
PID control helps reduce lateral error to the target path.
"""

from __future__ import annotations

import logging
import math
from typing import Sequence

logger = logging.getLogger(__name__)


class PIDController:
    """PID controller for lateral error correction."""

    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, error: float, dt: float) -> float:
        """Update PID and return correction term."""
        self.integral += error * dt
        derivative = (error - self.prev_error) / max(dt, 1e-6)
        self.prev_error = error
        return self.kp * error + self.ki * self.integral + self.kd * derivative

    def reset(self):
        """Reset integral and previous error."""
        self.integral = 0.0
        self.prev_error = 0.0


def _cum_dist(path: Sequence[tuple[float, float]]) -> list[float]:
    s = [0.0]
    for i in range(1, len(path)):
        x0, y0 = path[i - 1]
        x1, y1 = path[i]
        s.append(s[-1] + math.hypot(x1 - x0, y1 - y0))
    return s


def _nearest_idx(
    path: Sequence[tuple[float, float]],
    x: float,
    y: float,
    start: int,
    window: int = 80,
) -> int:
    end = min(len(path), start + window)
    best_i, best_d2 = start, float("inf")
    for i in range(start, end):
        dx, dy = path[i][0] - x, path[i][1] - y
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_i, best_d2 = i, d2
    return best_i


def _unwrap_angle(angle_rad: float, prev_rad: float) -> float:
    """Return angle_rad adjusted to be within ±pi of prev_rad (no 180° flip)."""
    diff = (angle_rad - prev_rad + math.pi) % (2.0 * math.pi) - math.pi
    return prev_rad + diff


def _lateral_error(
    path: Sequence[tuple[float, float]],
    x: float,
    y: float,
    idx: int,
) -> float:
    """Calculate signed lateral error (m) from vehicle to path. Positive = left of path."""
    if idx >= len(path) - 1:
        idx = len(path) - 2
    x0, y0 = path[idx]
    x1, y1 = path[idx + 1]
    # Vector along path segment
    dx_seg = x1 - x0
    dy_seg = y1 - y0
    seg_len = math.hypot(dx_seg, dy_seg)
    if seg_len < 1e-9:
        return 0.0
    # Vector from path point to vehicle
    dx_veh = x - x0
    dy_veh = y - y0
    # Cross product gives signed distance (perpendicular to path)
    cross = dx_seg * dy_veh - dy_seg * dx_veh
    return cross / seg_len


def follow_path(
    path_xy: Sequence[tuple[float, float]],
    wheelbase_m: float,
    step_m: float,
    lookahead_m: float,
    max_steer_deg: float,
    stop_lock_enabled: bool = True,
    rate_of_turn_deg_per_s: float = 15.0,
    speed_m_per_s: float = 1.39,  # ~5 km/h default
    pid_enabled: bool = False,
    pid_kp: float = 0.5,
    pid_ki: float = 0.0,
    pid_kd: float = 0.1,
    path_recovery_gain: float = 0.8,
    vehicle=None,
) -> tuple[list[tuple[float, float, float]], list[float], list[list[tuple[float, float, float]]] | None]:
    """
    Return front-axle poses, steer degrees, and segment_poses (if articulated).
    segment_poses[t][k] = (x,y,heading) for segment k at step t; N+1 segments for N articulations.
    """
    if len(path_xy) < 2:
        return [], [], None
    if wheelbase_m <= 1e-6:
        raise ValueError("wheelbase_m must be > 0")

    s = _cum_dist(path_xy)
    total = s[-1]
    steps = max(2, int(total / max(step_m, 1e-6)) + 1)

    # Initial pose: front axle at first path point, heading along first segment
    x0, y0 = path_xy[0]
    x1, y1 = path_xy[1]
    yaw = math.atan2(y1 - y0, x1 - x0)
    xr = x0 - wheelbase_m * math.cos(yaw)
    yr = y0 - wheelbase_m * math.sin(yaw)

    poses_front: list[tuple[float, float, float]] = []
    segment_poses: list[list[tuple[float, float, float]]] | None = None
    steer_hist: list[float] = []
    idx = 0
    sat_count = 0
    current_steer_deg = 0.0

    arts = getattr(vehicle, "articulation_positions_m", None) or (
        [vehicle.articulation_longitudinal_m] if vehicle and getattr(vehicle, "articulation_longitudinal_m", None) is not None else []
    )
    has_articulation = bool(arts)
    num_segments = len(arts) + 1 if arts else 0
    # Rear-most longitudinal position (for last segment)
    rear_most_long = (
        min((a.longitudinal_pos for a in vehicle.axles), default=arts[-1] - 2.0)
        if vehicle and arts else -2.0
    )
    # Previous articulation positions per segment (for stable heading computation)
    prev_art_x: list[float] = [0.0] * max(1, len(arts))
    prev_art_y: list[float] = [0.0] * max(1, len(arts))

    # Rate limiting: max change per step (deg)
    if not stop_lock_enabled and speed_m_per_s > 1e-6:
        dt_per_step = step_m / speed_m_per_s
        max_delta_deg_per_step = rate_of_turn_deg_per_s * dt_per_step
    else:
        dt_per_step = step_m / max(speed_m_per_s, 1e-6)
        max_delta_deg_per_step = float("inf")  # No rate limit when stop_lock enabled

    # PID controller for lateral error
    pid = PIDController(pid_kp, pid_ki, pid_kd) if pid_enabled else None

    for _ in range(steps):
        # Use steering axle (front) position for path tracking so we react as soon as it deviates
        xf = xr + wheelbase_m * math.cos(yaw)
        yf = yr + wheelbase_m * math.sin(yaw)
        idx = _nearest_idx(path_xy, xf, yf, idx)
        lat_err = _lateral_error(path_xy, xf, yf, idx)
        # Adaptive lookahead: when steering node is off path, shorten lookahead to aim back sooner
        if path_recovery_gain > 0:
            effective_lookahead = lookahead_m / (1.0 + path_recovery_gain * abs(lat_err))
            effective_lookahead = max(0.5, min(effective_lookahead, lookahead_m))
        else:
            effective_lookahead = lookahead_m
        target_s = min(total, s[idx] + effective_lookahead)
        j = idx
        while j < len(s) - 1 and s[j] < target_s:
            j += 1
        xt, yt = path_xy[j]

        # Pure pursuit: aim at target from rear axle (curvature from rear axle to target)
        dx, dy = xt - xr, yt - yr
        alpha = math.atan2(dy, dx) - yaw
        # wrap to [-pi, pi]
        alpha = (alpha + math.pi) % (2 * math.pi) - math.pi
        k_cmd = 2.0 * math.sin(alpha) / max(effective_lookahead, 1e-6)
        steer_cmd_rad = math.atan(wheelbase_m * k_cmd)
        steer_cmd_deg = math.degrees(steer_cmd_rad)

        # PID correction for lateral error (steering axle)
        if pid is not None:
            pid_correction_deg = pid.update(lat_err, dt_per_step)
            steer_cmd_deg += pid_correction_deg

        # Apply steering limits
        if abs(steer_cmd_deg) > max_steer_deg:
            sat_count += 1
            steer_cmd_deg = max_steer_deg if steer_cmd_deg > 0 else -max_steer_deg

        # Apply rate limiting if stop_lock is off
        if not stop_lock_enabled:
            delta_deg = steer_cmd_deg - current_steer_deg
            if abs(delta_deg) > max_delta_deg_per_step:
                delta_deg = max_delta_deg_per_step if delta_deg > 0 else -max_delta_deg_per_step
            steer_deg = current_steer_deg + delta_deg
            current_steer_deg = steer_deg
        else:
            steer_deg = steer_cmd_deg
            current_steer_deg = steer_deg

        steer_rad = math.radians(steer_deg)
        k = math.tan(steer_rad) / wheelbase_m
        yaw += step_m * k
        xr += step_m * math.cos(yaw)
        yr += step_m * math.sin(yaw)

        xf = xr + wheelbase_m * math.cos(yaw)
        yf = yr + wheelbase_m * math.sin(yaw)
        poses_front.append((xf, yf, yaw))
        steer_hist.append(steer_deg)

        # Multi-segment chain: each segment pivots around its front articulation, orients toward it
        if has_articulation and num_segments >= 1:
            if segment_poses is None:
                segment_poses = []
            row: list[tuple[float, float, float]] = [(xf, yf, yaw)]  # segment 0
            ax_cur, ay_cur = xf, yf
            h_cur = yaw
            for k in range(1, num_segments):
                art_x = ax_cur + arts[k - 1] * math.cos(h_cur)
                art_y = ay_cur + arts[k - 1] * math.sin(h_cur)
                if k < len(arts):
                    seg_len = arts[k - 1] - arts[k]
                else:
                    seg_len = arts[k - 1] - rear_most_long
                art_idx = k - 1
                if len(segment_poses) > 0 and art_idx < len(prev_art_x) and seg_len > 1e-6:
                    h_prev = segment_poses[-1][k][2]
                    dx = art_x - prev_art_x[art_idx]
                    dy = art_y - prev_art_y[art_idx]
                    # Pivot kinematics: dθ = (articulation lateral displacement) / L
                    # Trailer rear (axle centre) moves along longitudinal axis; can move transverse
                    lat_disp = dx * (-math.sin(h_prev)) + dy * math.cos(h_prev)
                    delta_theta = lat_disp / seg_len
                    h_k = h_prev + delta_theta
                    h_k = (h_k + math.pi) % (2.0 * math.pi) - math.pi
                    art_angle = (h_k - h_cur + math.pi) % (2.0 * math.pi) - math.pi
                    art_angle = max(-math.pi / 2.0, min(math.pi / 2.0, art_angle))
                    h_k = h_cur + art_angle
                    h_k = (h_k + math.pi) % (2.0 * math.pi) - math.pi
                    logger.debug("seg %d delta_theta_deg=%.2f art_angle_deg=%.1f", k, math.degrees(delta_theta), math.degrees(art_angle))
                else:
                    h_k = h_cur if len(segment_poses) == 0 else segment_poses[-1][k][2]
                row.append((art_x, art_y, h_k))
                prev_art_x[art_idx] = art_x
                prev_art_y[art_idx] = art_y
                ax_cur = art_x + seg_len * math.cos(h_k)
                ay_cur = art_y + seg_len * math.sin(h_k)
                h_cur = h_k
            segment_poses.append(row)

    if sat_count:
        logger.warning("Steering saturated %d/%d steps at ±%.1f°", sat_count, steps, max_steer_deg)
    return poses_front, steer_hist, segment_poses

