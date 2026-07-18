"""Matplotlib static plot: envelope, vehicle at start/end, path, carriageway. See PDR §2."""

import logging
from pathlib import Path
from typing import Sequence

from .envelope import body_outline_vehicle, transform_outline, swept_envelope_polygon
import math

logger = logging.getLogger(__name__)


def axle_positions_world(
    vehicle,
    steering_axle_x: float,
    steering_axle_y: float,
    heading_rad: float,
    segment_poses_row: Sequence[tuple[float, float, float]] | None = None,
) -> list[tuple[float, float, bool]]:
    """Return (x, y, is_steering) for each axle. segment_poses_row[k] = pose of segment k (origin + heading)."""
    axles = []
    for axle in vehicle.axles:
        seg = vehicle.get_segment_for_axle(axle)
        origin_m = vehicle.get_origin_for_segment(seg)
        if segment_poses_row is not None and seg < len(segment_poses_row):
            xo, yo, ho = segment_poses_row[seg]
        else:
            xo, yo, ho = steering_axle_x, steering_axle_y, heading_rad
        ax_rel_x = axle.longitudinal_pos - origin_m
        ax_rel_y = 0.0
        c, s = math.cos(ho), math.sin(ho)
        ax_world_x = xo + ax_rel_x * c - ax_rel_y * s
        ax_world_y = yo + ax_rel_x * s + ax_rel_y * c
        axles.append((ax_world_x, ax_world_y, axle.is_steering))
    return axles


def _wheel_centers(ax_x: float, ax_y: float, heading_rad: float, track_width: float
                   ) -> tuple[tuple[float, float], tuple[float, float]]:
    """Left and right wheel centers in world coords. Vehicle y positive = left."""
    half = track_width / 2
    # Perpendicular to heading: left = (+sin, -cos) in world if heading 0 → (1,0)
    # Vehicle left = +y → world left = (-sin(h), cos(h))
    dx = -math.sin(heading_rad) * half
    dy = math.cos(heading_rad) * half
    left = (ax_x + dx, ax_y + dy)
    right = (ax_x - dx, ax_y - dy)
    return left, right


def draw_wheel(ax, x: float, y: float, heading_rad: float, steer_rad: float,
               tyre_width: float, is_steering: bool):
    """Draw one wheel (rectangle) at (x,y). (x,y) is wheel center, not axle center."""
    wheel_length = tyre_width * 2.0   # Along axle (lateral)
    wheel_width = tyre_width * 1.2    # Perpendicular (rolling direction)
    wheel_angle = heading_rad + steer_rad if is_steering else heading_rad
    c_wheel, s_wheel = math.cos(wheel_angle), math.sin(wheel_angle)
    corners_rel = [
        (-wheel_length/2, -wheel_width/2),
        (wheel_length/2, -wheel_width/2),
        (wheel_length/2, wheel_width/2),
        (-wheel_length/2, wheel_width/2),
    ]
    corners_world = [
        (x + cx * c_wheel - cy * s_wheel, y + cx * s_wheel + cy * c_wheel)
        for cx, cy in corners_rel
    ]
    corners_world.append(corners_world[0])
    px, py = zip(*corners_world)
    color = "darkred" if is_steering else "darkgray"
    ax.plot(px, py, "-", lw=2, color=color, zorder=11)
    ax.fill(px, py, facecolor=color, alpha=0.6, zorder=11)


def save_plot(
    path_xy: Sequence[tuple[float, float]],
    positions: Sequence[tuple[float, float, float]],
    carriageway_xy: Sequence[tuple[float, float]] | None,
    out_path: str | Path,
    vehicle=None,
    steer_angles: Sequence[float] | None = None,
    segment_poses: Sequence[Sequence[tuple[float, float, float]]] | None = None,
) -> None:
    """Draw envelope, vehicle at start/end, steering path, carriageway; save to PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available; skipping plot")
        return
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    if carriageway_xy and len(carriageway_xy) >= 3:
        xs, ys = [p[0] for p in carriageway_xy], [p[1] for p in carriageway_xy]
        ax.fill(xs, ys, facecolor="0.92", edgecolor="gray", label="Carriageway")
    if vehicle and positions:
        envelope = swept_envelope_polygon(positions, vehicle, segment_poses=segment_poses)
        if envelope is not None and not envelope.is_empty:
            geoms = envelope.geoms if envelope.geom_type == "MultiPolygon" else [envelope]
            for i, g in enumerate(geoms):
                if hasattr(g, "exterior") and g.exterior and len(g.exterior.coords) >= 3:
                    ex = list(g.exterior.coords)
                    ax.fill([p[0] for p in ex], [p[1] for p in ex], facecolor="coral", alpha=0.5,
                            edgecolor="darkred", lw=1.5, label="Swept envelope" if i == 0 else None)
        has_segment_poses = (
            segment_poses is not None and len(segment_poses) == len(positions) and len(segment_poses[0]) > 1
        )

        def transform_body_outline(row: Sequence[tuple[float, float, float]] | None, x: float, y: float, h: float):
            """Return list of segment polygons: each segment = list of (x,y) points (closed)."""
            if row is None:
                outline = body_outline_vehicle(vehicle, segment_origin_m=0.0)
                return [transform_outline(outline, x, y, h)]
            segment_pts_list = []
            for seg_idx in range(len(row)):
                xk, yk, hk = row[seg_idx]
                body_k = vehicle.get_body_for_segment(seg_idx)
                origin_m = vehicle.get_origin_for_segment(seg_idx)
                outline = body_outline_vehicle(vehicle, body_k, segment_origin_m=origin_m)
                segment_pts_list.append(transform_outline(outline, xk, yk, hk))
            return segment_pts_list

        x0, y0, h0 = positions[0]
        row0 = segment_poses[0] if has_segment_poses and segment_poses else None
        start_segments = transform_body_outline(row0, x0, y0, h0)
        for si, seg_pts in enumerate(start_segments):
            if seg_pts:
                closed_x = [p[0] for p in seg_pts] + [seg_pts[0][0]]
                closed_y = [p[1] for p in seg_pts] + [seg_pts[0][1]]
                ax.plot(closed_x, closed_y, "g-", lw=2.5, label="Vehicle (start)" if si == 0 else None)
        x1, y1, h1 = positions[-1]
        row1 = segment_poses[-1] if has_segment_poses and segment_poses else None
        end_segments = transform_body_outline(row1, x1, y1, h1)
        for si, seg_pts in enumerate(end_segments):
            if seg_pts:
                closed_x = [p[0] for p in seg_pts] + [seg_pts[0][0]]
                closed_y = [p[1] for p in seg_pts] + [seg_pts[0][1]]
                ax.plot(closed_x, closed_y, "b-", lw=2.5, label="Vehicle (end)" if si == 0 else None)
        # Corner traces: per-segment corner count
        num_corners = 4 * vehicle.num_segments() if has_segment_poses else 4
        corner_traces = [[] for _ in range(num_corners)]
        for i in range(len(positions)):
            x, y, h = positions[i][0], positions[i][1], positions[i][2]
            row = segment_poses[i] if has_segment_poses and segment_poses and i < len(segment_poses) else None
            segment_pts_list = transform_body_outline(row, x, y, h)
            flat_pts = [p for seg in segment_pts_list for p in seg]
            for j, (px, py) in enumerate(flat_pts[:num_corners] if len(flat_pts) >= num_corners else flat_pts):
                if j < num_corners:
                    corner_traces[j].append((px, py))
        colors = ["orange", "purple", "brown", "pink"]
        for i, trace in enumerate(corner_traces):
            if len(trace) > 1:
                tx, ty = zip(*trace)
                ax.plot(tx, ty, "-", lw=1, alpha=0.4, color=colors[i % len(colors)],
                        label="Corner trace" if i == 0 else None)
        if len(positions) > 1:
            sx = [p[0] for p in positions]
            sy = [p[1] for p in positions]
            ax.plot(sx, sy, "-", lw=2, alpha=0.8, color="red", label="Steering axle trace")
        # Articulation points at start and end (all segment origins except segment 0)
        if has_segment_poses and segment_poses and len(segment_poses[0]) > 1:
            for seg_idx in range(1, len(segment_poses[0])):
                xa0, ya0, _ = segment_poses[0][seg_idx]
                xa1, ya1, _ = segment_poses[-1][seg_idx]
                ax.scatter([xa0], [ya0], s=100, c="orange", marker="D", edgecolors="black", linewidths=1.5,
                          label="Articulation" if seg_idx == 1 else None, zorder=12)
                ax.scatter([xa1], [ya1], s=100, c="orange", marker="D", edgecolors="black", linewidths=1.5, zorder=12)
        start_axles = axle_positions_world(vehicle, x0, y0, h0, segment_poses[0] if has_segment_poses and segment_poses else None)
        end_axles = axle_positions_world(vehicle, x1, y1, h1, segment_poses[-1] if has_segment_poses and segment_poses else None)
        steering_labeled = fixed_labeled = False
        for ax_x, ax_y, is_steer in start_axles:
            marker = "o" if is_steer else "s"
            size = 80 if is_steer else 60
            color = "red" if is_steer else "darkblue"
            label = ("Steering axle" if is_steer and not steering_labeled else None) or ("Fixed axle" if not is_steer and not fixed_labeled else None)
            if is_steer:
                steering_labeled = True
            else:
                fixed_labeled = True
            ax.scatter([ax_x], [ax_y], s=size, c=color, marker=marker, edgecolors="black", linewidths=1,
                      label=label, zorder=10)
        for ax_x, ax_y, is_steer in end_axles:
            marker = "o" if is_steer else "s"
            size = 80 if is_steer else 60
            color = "red" if is_steer else "blue"
            ax.scatter([ax_x], [ax_y], s=size, c=color, marker=marker, edgecolors="black", linewidths=1, zorder=10)
        if steer_angles and len(steer_angles) >= len(positions):
            for pos_idx in [0, len(positions) - 1]:
                x, y, h = positions[pos_idx]
                row = segment_poses[pos_idx] if has_segment_poses and segment_poses and pos_idx < len(segment_poses) else None
                primary_steer_deg = steer_angles[pos_idx] if pos_idx < len(steer_angles) else 0.0
                axles_world = axle_positions_world(vehicle, x, y, h, row)
                for i, (ax_x, ax_y, is_steer) in enumerate(axles_world):
                    axle_obj = vehicle.axles[i]
                    seg = vehicle.get_segment_for_axle(axle_obj)
                    wheel_heading = row[seg][2] if row and seg < len(row) else h
                    axle_steer_deg = vehicle.get_steer_angle_for_axle(i, primary_steer_deg)
                    wheel_steer = math.radians(axle_steer_deg)
                    left_center, right_center = _wheel_centers(ax_x, ax_y, wheel_heading, axle_obj.track_width)
                    draw_wheel(ax, left_center[0], left_center[1], wheel_heading, wheel_steer,
                              axle_obj.tyre_width, is_steer)
                    draw_wheel(ax, right_center[0], right_center[1], wheel_heading, wheel_steer,
                              axle_obj.tyre_width, is_steer)
    if path_xy:
        px, py = [p[0] for p in path_xy], [p[1] for p in path_xy]
        ax.plot(px, py, "k--", lw=1, alpha=0.7, label="Steering path")
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Swept path")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    logger.info("Saved plot: %s", out_path)


def save_animation(
    path_xy: Sequence[tuple[float, float]],
    positions: Sequence[tuple[float, float, float]],
    carriageway_xy: Sequence[tuple[float, float]] | None,
    out_path: str | Path,
    vehicle=None,
    fps: int = 10,
    steer_angles: Sequence[float] | None = None,
    segment_poses: Sequence[Sequence[tuple[float, float, float]]] | None = None,
) -> None:
    """Create animated GIF showing vehicle moving along path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, PillowWriter
    except ImportError:
        logger.warning("matplotlib not available; skipping animation")
        return
    if not vehicle or not positions:
        logger.warning("Vehicle and positions required for animation")
        return
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    # Static elements
    if carriageway_xy and len(carriageway_xy) >= 3:
        xs, ys = [p[0] for p in carriageway_xy], [p[1] for p in carriageway_xy]
        ax.fill(xs, ys, facecolor="0.92", edgecolor="gray", label="Carriageway")
    if path_xy:
        px, py = [p[0] for p in path_xy], [p[1] for p in path_xy]
        ax.plot(px, py, "k--", lw=1, alpha=0.5, label="Steering path")
    # Envelope (static)
    envelope = swept_envelope_polygon(positions, vehicle, segment_poses=segment_poses)
    if envelope is not None and not envelope.is_empty:
        geoms = envelope.geoms if envelope.geom_type == "MultiPolygon" else [envelope]
        for g in geoms:
            if hasattr(g, "exterior") and g.exterior and len(g.exterior.coords) >= 3:
                ex = list(g.exterior.coords)
                ax.fill([p[0] for p in ex], [p[1] for p in ex], facecolor="coral", alpha=0.3,
                        edgecolor="darkred", lw=1, label="Swept envelope")
    has_segment_poses = (
        segment_poses is not None and len(segment_poses) == len(positions) and len(segment_poses[0]) > 1
    )

    def transform_body_outline(row, x, y, h):
        """Return list of segment polygons: each segment = list of (x,y) points (closed)."""
        if row is None:
            outline = body_outline_vehicle(vehicle, segment_origin_m=0.0)
            return [transform_outline(outline, x, y, h)]
        segment_pts_list = []
        for seg_idx in range(len(row)):
            xk, yk, hk = row[seg_idx]
            body_k = vehicle.get_body_for_segment(seg_idx)
            origin_m = vehicle.get_origin_for_segment(seg_idx)
            outline = body_outline_vehicle(vehicle, body_k, segment_origin_m=origin_m)
            segment_pts_list.append(transform_outline(outline, xk, yk, hk))
        return segment_pts_list

    # Animated vehicle: one line and one fill per body segment
    num_seg = vehicle.num_segments() if has_segment_poses else 1
    vehicle_lines = [ax.plot([], [], "g-", lw=2.5, label="Vehicle" if i == 0 else None)[0] for i in range(num_seg)]
    vehicle_fills = []
    for _ in range(num_seg):
        fp = ax.fill([], [], facecolor="green", alpha=0.3, edgecolor="green", lw=2)
        if fp:
            vehicle_fills.append(fp[0])
    # Articulation markers (one per articulation)
    art_markers = []
    if has_segment_poses and segment_poses and len(segment_poses[0]) > 1:
        for _ in range(len(segment_poses[0]) - 1):
            m = ax.scatter([], [], s=100, c="orange", marker="D", edgecolors="black", linewidths=1.5, zorder=12, label="Articulation")
            art_markers.append(m)
    num_corners = 4 * vehicle.num_segments() if has_segment_poses else 4
    corner_traces = [[] for _ in range(num_corners)]
    corner_lines = []
    colors = ["orange", "purple", "brown", "pink"]
    for i in range(num_corners):
        line, = ax.plot([], [], "-", lw=1, alpha=0.4, color=colors[i % len(colors)])
        corner_lines.append(line)
    # Steering axle centre trace (accumulate)
    steering_axle_trace = []
    steering_axle_line, = ax.plot([], [], "-", lw=2, alpha=0.8, color="red", label="Steering axle trace")
    # Axle markers (animated)
    axle_scatters = []
    steering_labeled = False
    fixed_labeled = False
    for axle in vehicle.axles:
        marker = "o" if axle.is_steering else "s"
        size = 80 if axle.is_steering else 60
        label = None
        if axle.is_steering and not steering_labeled:
            label = "Steering axle"
            steering_labeled = True
        elif not axle.is_steering and not fixed_labeled:
            label = "Fixed axle"
            fixed_labeled = True
        scatter = ax.scatter([], [], s=size, c="red" if axle.is_steering else "blue",
                            marker=marker, edgecolors="black", linewidths=1, zorder=10, label=label)
        axle_scatters.append(scatter)
    # Wheel polygons (animated) - two per axle (left and right at track_width/2)
    wheel_polys = []
    for axle in vehicle.axles:
        for _ in (0, 1):  # left, right
            poly = ax.fill([], [], facecolor="darkred" if axle.is_steering else "darkgray",
                          edgecolor="darkred" if axle.is_steering else "darkgray", lw=2, alpha=0.6, zorder=11)[0]
            wheel_polys.append(poly)
    def animate(frame):
        if frame >= len(positions):
            ret = vehicle_lines + [steering_axle_line] + corner_lines + axle_scatters + wheel_polys + art_markers + vehicle_fills
            return ret
        x, y, h = positions[frame]
        row = segment_poses[frame] if has_segment_poses and segment_poses and frame < len(segment_poses) else None
        primary_steer_deg = steer_angles[frame] if steer_angles and frame < len(steer_angles) else 0.0
        steering_axle_trace.append((x, y))
        if len(steering_axle_trace) > 1:
            tx, ty = zip(*steering_axle_trace)
            steering_axle_line.set_data(tx, ty)
        for mi, art_m in enumerate(art_markers):
            if row and mi + 1 < len(row):
                xa, ya, _ = row[mi + 1]
                art_m.set_offsets([[xa, ya]])
        segment_pts_list = transform_body_outline(row, x, y, h)
        flat_pts = [p for seg in segment_pts_list for p in seg]
        for si, seg_pts in enumerate(segment_pts_list):
            if seg_pts and si < len(vehicle_lines):
                closed_x = [p[0] for p in seg_pts] + [seg_pts[0][0]]
                closed_y = [p[1] for p in seg_pts] + [seg_pts[0][1]]
                vehicle_lines[si].set_data(closed_x, closed_y)
            if seg_pts and si < len(vehicle_fills):
                vehicle_fills[si].set_xy(list(zip([p[0] for p in seg_pts] + [seg_pts[0][0]], [p[1] for p in seg_pts] + [seg_pts[0][1]])))
        for j, (px_c, py_c) in enumerate(flat_pts[:num_corners] if len(flat_pts) >= num_corners else flat_pts):
            if j < num_corners:
                corner_traces[j].append((px_c, py_c))
                if len(corner_traces[j]) > 1:
                    tx, ty = zip(*corner_traces[j])
                    corner_lines[j].set_data(tx, ty)
        axles_world = axle_positions_world(vehicle, x, y, h, row)
        wp_idx = 0
        for i, (ax_x, ax_y, is_steer) in enumerate(axles_world):
            axle_obj = vehicle.axles[i]
            wheel_length = axle_obj.tyre_width * 2.0
            wheel_width = axle_obj.tyre_width * 1.2
            axle_scatters[i].set_offsets([[ax_x, ax_y]])
            axle_steer_deg = vehicle.get_steer_angle_for_axle(i, primary_steer_deg)
            wheel_steer = math.radians(axle_steer_deg)
            seg = vehicle.get_segment_for_axle(axle_obj)
            wheel_heading = row[seg][2] if row and seg < len(row) else h
            wheel_angle = wheel_heading + wheel_steer if is_steer else wheel_heading
            c_wheel, s_wheel = math.cos(wheel_angle), math.sin(wheel_angle)
            left_center, right_center = _wheel_centers(ax_x, ax_y, wheel_heading, axle_obj.track_width)
            for wx, wy in (left_center, right_center):
                corners_rel = [
                    (-wheel_length/2, -wheel_width/2),
                    (wheel_length/2, -wheel_width/2),
                    (wheel_length/2, wheel_width/2),
                    (-wheel_length/2, wheel_width/2),
                ]
                corners_world = [
                    (wx + cx * c_wheel - cy * s_wheel, wy + cx * s_wheel + cy * c_wheel)
                    for cx, cy in corners_rel
                ]
                wheel_polys[wp_idx].set_xy(corners_world)
                wp_idx += 1
        ret = vehicle_lines + [steering_axle_line] + corner_lines + axle_scatters + wheel_polys + art_markers + vehicle_fills
        return ret
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Swept path animation")
    # Set axis limits
    all_x = [p[0] for p in positions] + ([p[0] for p in path_xy] if path_xy else [])
    all_y = [p[1] for p in positions] + ([p[1] for p in path_xy] if path_xy else [])
    if all_x and all_y:
        margin = max(max(all_x) - min(all_x), max(all_y) - min(all_y)) * 0.1
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
    anim = FuncAnimation(fig, animate, frames=len(positions), interval=1000//fps, blit=True, repeat=True)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PillowWriter(fps=fps)
    anim.save(str(out_path), writer=writer)
    plt.close(fig)
    logger.info("Saved animation: %s (%d frames, %d fps)", out_path, len(positions), fps)
