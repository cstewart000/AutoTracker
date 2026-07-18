"""Plots and GIF for vertical profile mode: chainage →, elevation ↑."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import numpy as np

from .vertical_geometry import (
    articulation_wheel_xy,
    segment_profile_polygons,
    trailer_central_pivot_xy,
)
from .vehicle import VerticalProfile
from .vertical_sim import VerticalFrame

if TYPE_CHECKING:
    from .vehicle import Vehicle

logger = logging.getLogger(__name__)


def profile_swept_extent_polygon(
    frames: Sequence[VerticalFrame],
    vp: VerticalProfile,
    vehicle: "Vehicle",
    path: np.ndarray,
) -> list[tuple[float, float]] | None:
    """Union of rotated segment body polygons over all frames; exterior ring in (chainage, elevation)."""
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except ImportError:
        logger.warning("shapely not available; skipping profile swept extent")
        return None
    polys = []
    for fr in frames:
        for seg_poly in segment_profile_polygons(vehicle, fr, vp, path):
            if len(seg_poly) >= 4:
                polys.append(Polygon(seg_poly))
    if not polys:
        return None
    u = unary_union(polys)
    if u.is_empty:
        return None
    if u.geom_type == "Polygon":
        return list(u.exterior.coords)
    if u.geom_type == "MultiPolygon":
        g = max(u.geoms, key=lambda x: getattr(x, "area", 0.0))
        return list(g.exterior.coords)
    return None


def save_vertical_plot(
    path_sz: Sequence[tuple[float, float]],
    frames: Sequence[VerticalFrame],
    out_path: str | Path,
    vp: VerticalProfile,
    vehicle: "Vehicle",
    path: np.ndarray,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available; skipping vertical plot")
        return
    if not frames:
        return
    extent = profile_swept_extent_polygon(frames, vp, vehicle, path)
    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    px = [p[0] for p in path_sz]
    pz = [p[1] for p in path_sz]
    if extent:
        ex, ez = zip(*extent)
        ax.fill(ex, ez, facecolor="coral", alpha=0.4, edgecolor="darkred", lw=1.5, zorder=1, label="Swept profile extent")
    ax.plot(px, pz, "k-", lw=2, label="Ground profile", zorder=3)
    fr0, fr1 = frames[0], frames[-1]
    for lab, fr, c in (("Start", fr0, "green"), ("End", fr1, "blue")):
        for s, zg, zw in zip(fr.axle_s, fr.z_ground, fr.z_wheel_center):
            circ = plt.Circle((s, zw), vp.wheel_radius_m, fill=False, ec=c, lw=2, zorder=5)
            ax.add_patch(circ)
        for spi, seg_poly in enumerate(segment_profile_polygons(vehicle, fr, vp, path)):
            sx = [p[0] for p in seg_poly]
            sz = [p[1] for p in seg_poly]
            lbl = f"Body seg{spi} ({lab})" if spi > 0 else f"Body ({lab})"
            ax.fill(sx, sz, facecolor=c, alpha=0.25, edgecolor=c, lw=1.5, label=lbl, zorder=4)
        art = articulation_wheel_xy(vehicle, fr, path, vp.wheel_radius_m)
        if art:
            ax.scatter(
                [art[0]], [art[1]], s=120, c="purple", marker="D", edgecolors="black", linewidths=1,
                zorder=15, label=f"Articulation ({lab})",
            )
        piv = trailer_central_pivot_xy(vehicle, fr)
        if piv:
            ax.scatter(
                [piv[0]], [piv[1]], s=200, c="darkorange", marker="*", edgecolors="black", linewidths=1,
                zorder=16, label=f"Trailer pivot — central axle ({lab})",
            )
    ax.set_xlabel("Chainage (m) →")
    ax.set_ylabel("Elevation (m)")
    ax.set_title("Vertical profile — tractor chord; trailer pivots at central axle (hinges marked)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved vertical plot: %s", out_path)


def save_vertical_animation(
    path_sz: Sequence[tuple[float, float]],
    frames: Sequence[VerticalFrame],
    out_path: str | Path,
    vp: VerticalProfile,
    vehicle: "Vehicle",
    path: np.ndarray,
    fps: int = 10,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, PillowWriter
    except ImportError:
        logger.warning("matplotlib not available; skipping vertical animation")
        return
    if not frames:
        return
    extent = profile_swept_extent_polygon(frames, vp, vehicle, path)
    px = [p[0] for p in path_sz]
    pz = [p[1] for p in path_sz]
    all_s = [s for fr in frames for s in fr.axle_s]
    all_z = [z for fr in frames for z in fr.z_wheel_center]
    margin = max(1.0, (max(px) - min(px)) * 0.05)
    xlim = (min(min(px), min(all_s, default=min(px))) - margin, max(max(px), max(all_s, default=max(px))) + margin)
    zmin = min(min(pz), min(all_z, default=min(pz)) - vp.wheel_radius_m * 2)
    zmax = max(max(pz), max(all_z, default=max(pz)) + vp.wheel_radius_m + 4.0)
    zlim = (zmin - margin, zmax + margin)
    fig, ax = plt.subplots(1, 1, figsize=(12, 5))

    def animate(i):
        ax.clear()
        if extent:
            ex, ez = zip(*extent)
            ax.fill(ex, ez, facecolor="coral", alpha=0.35, edgecolor="darkred", lw=1, zorder=1)
        ax.plot(px, pz, "k-", lw=2, zorder=3)
        fr = frames[min(i, len(frames) - 1)]
        for s, zw in zip(fr.axle_s, fr.z_wheel_center):
            c = plt.Circle((s, zw), vp.wheel_radius_m, fill=False, ec="darkgreen", lw=2, zorder=5)
            ax.add_patch(c)
        for seg_poly in segment_profile_polygons(vehicle, fr, vp, path):
            sx = [p[0] for p in seg_poly]
            sz = [p[1] for p in seg_poly]
            ax.fill(sx, sz, facecolor="green", alpha=0.4, edgecolor="darkgreen", lw=1.2, zorder=4)
        art = articulation_wheel_xy(vehicle, fr, path, vp.wheel_radius_m)
        if art:
            ax.scatter([art[0]], [art[1]], s=130, c="purple", marker="D", edgecolors="black", linewidths=1, zorder=15)
        piv = trailer_central_pivot_xy(vehicle, fr)
        if piv:
            ax.scatter([piv[0]], [piv[1]], s=220, c="darkorange", marker="*", edgecolors="black", linewidths=1, zorder=16)
        ax.set_xlim(xlim)
        ax.set_ylim(zlim)
        ax.set_xlabel("Chainage (m) →")
        ax.set_ylabel("Elevation (m)")
        ax.set_title("Vertical profile — purple: articulation, *: trailer central-axle pivot")
        ax.grid(True, alpha=0.3)

    anim = FuncAnimation(fig, animate, frames=len(frames), interval=1000 // max(1, fps), blit=False)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(out_path), writer=PillowWriter(fps=fps))
    plt.close(fig)
    logger.info("Saved vertical animation: %s", out_path)
