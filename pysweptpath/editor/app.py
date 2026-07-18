"""Tkinter vehicle editor: Open XML draws geometry; tools add axles/body. See PDR §3.3."""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path

from ..vehicle import load_vehicle, write_vehicle, Vehicle, Body, Axle
from .canvas_draw import (
    draw_vehicle, draw_axle, draw_body_rect, draw_body_polygon, draw_steering_origin,
    draw_articulation, vehicle_bbox, bbox_to_view,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

# Editable state when building vehicle (not from file)
axles_edit: list[tuple[float, float, bool]] = []  # (long_pos, track, is_steering)
body_pts_edit: list[tuple[float, float]] = []
body_rect: tuple[float, float, float] | None = None  # (width, front, rear) or None
articulation_edit: float | None = None  # longitudinal position (m) or None
current_vehicle = None  # set when Open XML, cleared on New or when using tools


def redraw(canvas: tk.Canvas, vehicle=None) -> None:
    global current_vehicle
    current_vehicle = vehicle
    canvas.delete("all")
    w = max(1, canvas.winfo_width())
    h = max(1, canvas.winfo_height())
    x_min, y_min, x_max, y_max = vehicle_bbox(
        axles_edit, body_rect, body_pts_edit, articulation_edit, vehicle=current_vehicle
    )
    view = bbox_to_view(x_min, y_min, x_max, y_max, w, h)
    canvas.create_text(w / 2, 18, text="Plan view — x=forward, y=left (auto-centred)", fill="gray")
    if current_vehicle is not None:
        draw_vehicle(canvas, current_vehicle, view=view)
        logger.info("Drew loaded vehicle: %s", current_vehicle.name)
        return
    for long_pos, track, is_steer in axles_edit:
        draw_axle(canvas, long_pos, track, is_steer, view=view)
    if body_rect:
        draw_body_rect(canvas, body_rect[0], body_rect[1], body_rect[2], view=view)
    elif len(body_pts_edit) >= 2:
        draw_body_polygon(canvas, body_pts_edit, view=view)
    if articulation_edit is not None:
        draw_articulation(canvas, articulation_edit, view=view)
    draw_steering_origin(canvas, view=view)


def on_open_xml(canvas: tk.Canvas) -> None:
    path = filedialog.askopenfilename(filetypes=[("XML", "*.xml")], title="Open vehicle XML")
    if not path:
        return
    try:
        vehicle = load_vehicle(path)
        redraw(canvas, vehicle=vehicle)
        logger.info("Loaded and drew: %s", path)
    except Exception as e:
        messagebox.showerror("Load error", str(e))
        logger.exception("Load failed: %s", path)


def on_place_steering(canvas: tk.Canvas) -> None:
    axles_edit.insert(0, (0.0, 2.05, True))
    redraw(canvas, vehicle=None)


def on_add_fixed_axle(canvas: tk.Canvas) -> None:
    pos = simpledialog.askfloat("Fixed axle", "Longitudinal position (m, negative = rear):", initialvalue=-4.0)
    if pos is None:
        return
    track = simpledialog.askfloat("Track", "Track width (m):", initialvalue=2.05)
    if track is None:
        return
    axles_edit.append((pos, track, False))
    redraw(canvas, vehicle=None)
    logger.info("Added fixed axle at %s m, track %s", pos, track)


def on_rectangle_body(canvas: tk.Canvas) -> None:
    w = simpledialog.askfloat("Body", "Width (m):", initialvalue=2.6)
    if w is None:
        return
    front = simpledialog.askfloat("Body", "Front overhang (m):", initialvalue=1.2)
    if front is None:
        return
    rear = simpledialog.askfloat("Body", "Rear overhang (m):", initialvalue=2.1)
    if rear is None:
        return
    global body_rect
    body_rect = (w, front, rear)
    body_pts_edit.clear()
    redraw(canvas, vehicle=None)


def on_click_polygon(canvas: tk.Canvas, event) -> None:
    # Map canvas coords to vehicle metres (inverse of to_canvas)
    cx, cy = canvas.winfo_width() / 2, canvas.winfo_height() / 2
    from .canvas_draw import SCALE
    x_m = (event.x - cx) / SCALE
    y_m = -(event.y - cy) / SCALE
    body_pts_edit.append((x_m, y_m))
    redraw(canvas, vehicle=None)
    logger.info("Body point %s: (%.2f, %.2f)", len(body_pts_edit), x_m, y_m)


def on_draw_polygon(canvas: tk.Canvas) -> None:
    body_pts_edit.clear()
    global body_rect
    body_rect = None
    canvas.bind("<Button-1>", lambda e: on_click_polygon(canvas, e))
    messagebox.showinfo("Draw body", "Click points on canvas to add body polygon. Then use another tool to stop.")


def on_set_articulation(canvas: tk.Canvas) -> None:
    global articulation_edit
    val = simpledialog.askfloat(
        "Articulation point",
        "Longitudinal position (m, negative = rear of steering axle):\nPivot for articulated units.",
        initialvalue=articulation_edit if articulation_edit is not None else -2.0,
    )
    if val is None:
        return
    articulation_edit = val
    redraw(canvas, vehicle=None)
    logger.info("Articulation point at %.2f m", articulation_edit)


def on_clear_articulation(canvas: tk.Canvas) -> None:
    global articulation_edit
    articulation_edit = None
    redraw(canvas, vehicle=None)


def _vehicle_from_edit_state() -> Vehicle | None:
    """Build Vehicle from axles_edit and body_rect/body_pts_edit if enough data."""
    if not axles_edit:
        return None
    axles = []
    for i, (long_pos, track, is_steer) in enumerate(axles_edit):
        axles.append(Axle(index=i, longitudinal_pos=long_pos, is_steering=is_steer, track_width=track))
    if body_rect:
        body = Body(width=body_rect[0], front_overhang=body_rect[1], rear_overhang=body_rect[2])
    elif len(body_pts_edit) >= 2:
        body = Body(width=2.6, front_overhang=1.2, rear_overhang=2.1, polygon=body_pts_edit.copy())
    else:
        body = Body(width=2.6, front_overhang=1.2, rear_overhang=2.1)
    return Vehicle(name="Edited", version="1.0", body=body, axles=axles,
                   articulation_longitudinal_m=articulation_edit)


def on_save_xml(canvas: tk.Canvas) -> None:
    path = filedialog.asksaveasfilename(
        defaultextension=".xml",
        filetypes=[("XML", "*.xml"), ("All files", "*.*")],
        title="Save vehicle as XML",
    )
    if not path:
        return
    try:
        if current_vehicle is not None:
            write_vehicle(current_vehicle, path)
        else:
            v = _vehicle_from_edit_state()
            if v is None:
                messagebox.showwarning("Save", "Add at least one axle (Place steering axle) before saving.")
                return
            write_vehicle(v, path)
        messagebox.showinfo("Save", f"Saved to {path}")
        logger.info("Saved vehicle to %s", path)
    except Exception as e:
        messagebox.showerror("Save error", str(e))
        logger.exception("Save failed: %s", path)


def main() -> None:
    root = tk.Tk()
    root.title("pySweptPath Vehicle Editor")
    root.geometry("900x600")

    menubar = tk.Menu(root)
    root.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)

    main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
    main_pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    canvas_frame = ttk.LabelFrame(main_pane, text="Plan view (1:50)")
    main_pane.add(canvas_frame, weight=2)
    canvas = tk.Canvas(canvas_frame, bg="white")
    canvas.pack(fill=tk.BOTH, expand=True)

    def do_redraw(_=None):
        redraw(canvas, vehicle=current_vehicle if current_vehicle is not None else None)
    canvas.bind("<Configure>", do_redraw)

    def on_new():
        global axles_edit, body_pts_edit, body_rect, articulation_edit, current_vehicle
        current_vehicle = None
        axles_edit.clear()
        body_pts_edit.clear()
        body_rect = None
        articulation_edit = None
        redraw(canvas, vehicle=None)
        logger.info("New vehicle")
    file_menu.add_command(label="New vehicle", command=on_new)
    file_menu.add_command(label="Open XML...", command=lambda: on_open_xml(canvas))
    file_menu.add_command(label="Save XML...", command=lambda: on_save_xml(canvas))
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)

    tools_frame = ttk.LabelFrame(main_pane, text="Tools")
    main_pane.add(tools_frame, weight=1)
    ttk.Button(tools_frame, text="Place steering axle", command=lambda: on_place_steering(canvas)).pack(pady=2, fill=tk.X)
    ttk.Button(tools_frame, text="Add fixed axle", command=lambda: on_add_fixed_axle(canvas)).pack(pady=2, fill=tk.X)
    ttk.Button(tools_frame, text="Draw body polygon", command=lambda: on_draw_polygon(canvas)).pack(pady=2, fill=tk.X)
    ttk.Button(tools_frame, text="Rectangle body", command=lambda: on_rectangle_body(canvas)).pack(pady=2, fill=tk.X)
    ttk.Button(tools_frame, text="Set articulation point", command=lambda: on_set_articulation(canvas)).pack(pady=2, fill=tk.X)
    ttk.Button(tools_frame, text="Clear articulation", command=lambda: on_clear_articulation(canvas)).pack(pady=2, fill=tk.X)
    ttk.Separator(tools_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
    ttk.Label(tools_frame, text="Track width (m):").pack(anchor=tk.W)
    ttk.Entry(tools_frame, width=10).pack(fill=tk.X, pady=2)
    ttk.Label(tools_frame, text="Max steer (deg):").pack(anchor=tk.W)
    ttk.Entry(tools_frame, width=10).pack(fill=tk.X, pady=2)
    ttk.LabelFrame(tools_frame, text="Ackermann preview").pack(fill=tk.X, pady=8)

    redraw(canvas, vehicle=None)
    logger.info("Vehicle editor started")
    root.mainloop()


if __name__ == "__main__":
    main()
