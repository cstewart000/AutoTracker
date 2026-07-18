"""Canvas coordinate mapping and draw vehicle/axles/body. Scale 1:50 (m -> px)."""

import tkinter as tk
from typing import Sequence

from ..envelope import body_outline_vehicle

# Vehicle: x = forward, y = left. Canvas: origin centre, x right, y up.
SCALE = 50  # px per metre (1:50)
# view = (center_x_m, center_y_m, scale_px_per_m) or None for default (0,0, SCALE)
View = tuple[float, float, float] | None


def to_canvas(canvas: tk.Canvas, x_m: float, y_m: float, view: View = None) -> tuple[int, int]:
    w = max(1, canvas.winfo_width())
    h = max(1, canvas.winfo_height())
    if view:
        cx_m, cy_m, scale = view
        px = w / 2 + (x_m - cx_m) * scale
        py = h / 2 - (y_m - cy_m) * scale
    else:
        px = w / 2 + x_m * SCALE
        py = h / 2 - y_m * SCALE
    return int(px), int(py)


def draw_axle(canvas: tk.Canvas, long_pos_m: float, track_width_m: float, is_steering: bool,
              view: View = None) -> None:
    half = track_width_m / 2
    p1 = to_canvas(canvas, long_pos_m, -half, view)
    p2 = to_canvas(canvas, long_pos_m, half, view)
    color = "blue" if is_steering else "black"
    canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=color, width=3)
    pc = to_canvas(canvas, long_pos_m, 0, view)
    r = 4
    canvas.create_oval(pc[0] - r, pc[1] - r, pc[0] + r, pc[1] + r, fill=color, outline=color)


def draw_body_rect(canvas: tk.Canvas, width: float, front: float, rear: float, view: View = None) -> None:
    pts = [(-rear, -width / 2), (front, -width / 2), (front, width / 2), (-rear, width / 2)]
    canvas_pts = [to_canvas(canvas, x, y, view) for x, y in pts]
    flat = [c for p in canvas_pts for c in p]
    canvas.create_polygon(flat, fill="", outline="green", width=2)


def draw_body_polygon(canvas: tk.Canvas, points: Sequence[tuple[float, float]], view: View = None) -> None:
    if len(points) < 2:
        return
    canvas_pts = [to_canvas(canvas, x, y, view) for x, y in points]
    flat = [c for p in canvas_pts for c in p]
    canvas.create_polygon(flat, fill="", outline="green", width=2)


def draw_steering_origin(canvas: tk.Canvas, view: View = None) -> None:
    pc = to_canvas(canvas, 0, 0, view)
    r = 8
    canvas.create_oval(pc[0] - r, pc[1] - r, pc[0] + r, pc[1] + r, fill="red", outline="darkred", width=2)
    canvas.create_text(pc[0], pc[1] - 14, text="(0,0) steering", font=("", 9), fill="red")


def draw_articulation(canvas: tk.Canvas, longitudinal_m: float, view: View = None) -> None:
    """Draw articulation point (pivot) as a diamond at (longitudinal_m, 0)."""
    pc = to_canvas(canvas, longitudinal_m, 0, view)
    r = 10
    pts = [(pc[0], pc[1] - r), (pc[0] + r, pc[1]), (pc[0], pc[1] + r), (pc[0] - r, pc[1])]
    flat = [c for p in pts for c in p]
    canvas.create_polygon(flat, fill="orange", outline="darkorange", width=2)
    canvas.create_text(pc[0], pc[1] + r + 12, text="Articulation", font=("", 8), fill="darkorange")


def vehicle_bbox(axles_edit: list, body_rect: tuple | None, body_pts_edit: list,
                articulation_m: float | None, vehicle=None) -> tuple[float, float, float, float]:
    """Return (x_min, y_min, x_max, y_max) in vehicle coords for recentering."""
    xs, ys = [0.0], [0.0]  # steering origin
    if vehicle:
        for a in vehicle.axles:
            half = a.track_width / 2
            xs.extend([a.longitudinal_pos, a.longitudinal_pos])
            ys.extend([-half, half])
        num_seg = vehicle.num_segments()
        if num_seg > 1 and (vehicle.body_segments or (vehicle.front_body and vehicle.rear_body)):
            for seg_idx in range(num_seg):
                origin_m = vehicle.get_origin_for_segment(seg_idx)
                body = vehicle.get_body_for_segment(seg_idx)
                outline_local = body_outline_vehicle(vehicle, body, segment_origin_m=origin_m)
                for x, y in outline_local:
                    xs.append(x + origin_m); ys.append(y)
        elif vehicle.body.polygon:
            for x, y in vehicle.body.polygon:
                xs.append(x); ys.append(y)
        else:
            w2 = vehicle.body.width / 2
            xs.extend([-vehicle.body.rear_overhang, vehicle.body.front_overhang])
            ys.extend([-w2, w2])
        arts = vehicle._art_list() if hasattr(vehicle, "_art_list") else (
            [vehicle.articulation_longitudinal_m] if getattr(vehicle, "articulation_longitudinal_m", None) is not None else []
        )
        for art_m in arts:
            xs.append(art_m)
            ys.append(0.0)
    for long_pos, track, _ in axles_edit:
        half = track / 2
        xs.extend([long_pos, long_pos]); ys.extend([-half, half])
    if body_rect:
        w2 = body_rect[0] / 2
        xs.extend([-body_rect[2], body_rect[1]])
        ys.extend([-w2, w2])
    for x, y in body_pts_edit:
        xs.append(x); ys.append(y)
    if articulation_m is not None:
        xs.append(articulation_m); ys.append(0.0)
    if not xs or not ys:
        return -5.0, -5.0, 5.0, 5.0
    margin = 2.0
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def bbox_to_view(x_min: float, y_min: float, x_max: float, y_max: float,
                 canvas_w: int, canvas_h: int) -> tuple[float, float, float]:
    """Return (center_x_m, center_y_m, scale_px_per_m) to fit bbox in canvas."""
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    dx = max(x_max - x_min, 1.0)
    dy = max(y_max - y_min, 1.0)
    scale = min(canvas_w / dx, canvas_h / dy, 80)  # cap scale for very small content
    scale = max(scale, 10)
    return (cx, cy, scale)


def draw_vehicle(canvas: tk.Canvas, vehicle, view: View = None) -> None:
    """Draw loaded Vehicle: axles, body/body segments, origin, articulations."""
    for axle in vehicle.axles:
        draw_axle(canvas, axle.longitudinal_pos, axle.track_width, axle.is_steering, view)
    num_seg = vehicle.num_segments()
    if num_seg > 1 and (vehicle.body_segments or (vehicle.front_body and vehicle.rear_body)):
        for seg_idx in range(num_seg):
            origin_m = vehicle.get_origin_for_segment(seg_idx)
            body = vehicle.get_body_for_segment(seg_idx)
            outline_local = body_outline_vehicle(vehicle, body, segment_origin_m=origin_m)
            global_pts = [(x + origin_m, y) for x, y in outline_local]
            draw_body_polygon(canvas, global_pts, view)
    elif vehicle.body.polygon and len(vehicle.body.polygon) >= 2:
        draw_body_polygon(canvas, vehicle.body.polygon, view)
    else:
        draw_body_rect(canvas, vehicle.body.width, vehicle.body.front_overhang,
                      vehicle.body.rear_overhang, view)
    arts = vehicle._art_list() if hasattr(vehicle, "_art_list") else (
        [vehicle.articulation_longitudinal_m] if getattr(vehicle, "articulation_longitudinal_m", None) is not None else []
    )
    for art_m in arts:
        draw_articulation(canvas, art_m, view)
    draw_steering_origin(canvas, view)
