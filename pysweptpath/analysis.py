"""Programmatic analysis API shared by CLI and web. See PLANNED_FEATURES A1."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

from .clearance import ClearanceResult, compute_clearance
from .config import ProjectConfig, load_config
from .dxf_io import load_dxf, read_carriageway_hatch, read_steering_path
from .envelope import swept_envelope_polygon
from .kinematics import densify_path
from .path_follow import follow_path
from .plot_output import save_animation, save_plot
from .report import (
    ReportData,
    build_report,
    write_json_report,
    write_text_report,
    write_vertical_json_report,
    write_vertical_text_report,
)
from .vehicle import load_vehicle

logger = logging.getLogger(__name__)


def report_subdir_name(name: str) -> str:
    """Safe single path segment for reports/ subfolders."""
    s = name.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "run"


@dataclass
class AnalysisResult:
    """Structured result of a swept-path (or vertical profile) run."""

    ok: bool
    mode: str  # "plan" | "vertical"
    vehicle_name: str
    report: dict[str, Any]
    run_dir: Path
    path_pts: list[tuple[float, float]] = field(default_factory=list)
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    steer_angles_deg: list[float] = field(default_factory=list)
    envelope_outer: list[tuple[float, float]] | None = None
    carriageway_xy: list[tuple[float, float]] | None = None
    plot_path: Path | None = None
    animation_path: Path | None = None
    dxf_path: Path | None = None
    report_json_path: Path | None = None
    report_text_path: Path | None = None
    message: str = ""
    max_steer_deg: float = 0.0
    min_radius_m: float = 0.0
    clearance: ClearanceResult | None = None

    def to_public_dict(self, *, base_url: str = "") -> dict[str, Any]:
        """JSON-serializable summary for the web API."""
        def rel(p: Path | None) -> str | None:
            if p is None or not p.exists():
                return None
            return str(p)

        out = {
            "ok": self.ok,
            "mode": self.mode,
            "vehicle_name": self.vehicle_name,
            "report": self.report,
            "message": self.message,
            "max_steer_deg": self.max_steer_deg,
            "min_radius_m": self.min_radius_m,
            "path_pts": self.path_pts,
            "positions_sample": _downsample_positions(self.positions, 200),
            "envelope_outer": self.envelope_outer,
            "carriageway_xy": self.carriageway_xy,
            "files": {
                "plot": rel(self.plot_path),
                "animation": rel(self.animation_path),
                "dxf": rel(self.dxf_path),
                "report_json": rel(self.report_json_path),
                "report_text": rel(self.report_text_path),
                "run_dir": str(self.run_dir),
            },
        }
        if self.clearance is not None:
            out["clearance"] = {
                "encroachment_area_m2": self.clearance.encroachment_area_m2,
                "max_penetration_m": self.clearance.max_penetration_m,
                "has_encroachment": self.clearance.has_encroachment,
                "min_lateral_clearance_m": self.clearance.min_lateral_clearance_m,
            }
        return out


def _downsample_positions(
    positions: Sequence[tuple[float, float, float]], max_n: int
) -> list[list[float]]:
    if not positions:
        return []
    if len(positions) <= max_n:
        return [[float(p[0]), float(p[1]), float(p[2])] for p in positions]
    step = max(1, len(positions) // max_n)
    sampled = positions[::step]
    if sampled[-1] is not positions[-1]:
        sampled = list(sampled) + [positions[-1]]
    return [[float(p[0]), float(p[1]), float(p[2])] for p in sampled]


def _envelope_ring(env) -> list[tuple[float, float]] | None:
    if env is None or getattr(env, "is_empty", True):
        return None
    geom = env
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: getattr(g, "area", 0.0))
    if hasattr(geom, "exterior"):
        return [(float(x), float(y)) for x, y in geom.exterior.coords]
    return None


def run_analysis(
    config_path: str | Path | None = None,
    *,
    cfg: ProjectConfig | None = None,
    output_dir: str | Path | None = None,
    dxf_out: str | Path | None = None,
    animation: bool | None = None,
    write_files: bool = True,
) -> AnalysisResult:
    """
    Run plan or vertical swept-path analysis from config.

    Provide either ``config_path`` or a pre-loaded ``cfg``.
    When ``output_dir`` is set, reports land there instead of
    ``<config_dir>/reports/<input>/<vehicle>/``.
    """
    if cfg is None:
        if config_path is None:
            raise ValueError("Provide config_path or cfg")
        cfg = load_config(config_path)
        config_dir = Path(config_path).resolve().parent
    else:
        config_dir = Path(config_path).resolve().parent if config_path else Path.cwd()

    if animation is not None:
        cfg = replace(cfg, output=replace(cfg.output, animation=animation))

    logger.info("Design vehicle: %s", cfg.design_vehicle)
    design = load_vehicle(cfg.design_vehicle)

    path_pts: list[tuple[float, float]] | None = None
    carriageway = None
    doc = load_dxf(cfg.dxf.input_file) if cfg.dxf.input_file else None
    if doc:
        path_pts = read_steering_path(doc, cfg.dxf.steering_layer)
        carriageway = read_carriageway_hatch(doc, cfg.dxf.carriageway_layer)
    if not path_pts or len(path_pts) < 2:
        if not doc:
            logger.warning(
                "DXF file not found: %s – using default 10 m path.",
                cfg.dxf.input_file,
            )
        else:
            logger.warning(
                "No steering path on layer %s – using default path.",
                cfg.dxf.steering_layer,
            )
        path_pts = [(0.0, 0.0), (10.0, 0.0), (20.0, 5.0)]

    if output_dir is not None:
        run_dir = Path(output_dir)
    else:
        in_seg = (
            report_subdir_name(Path(cfg.dxf.input_file).stem)
            if cfg.dxf.input_file
            else "no_input"
        )
        veh_seg = report_subdir_name(Path(cfg.design_vehicle).stem)
        run_dir = config_dir / "reports" / in_seg / veh_seg
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", run_dir)

    if cfg.simulation.vertical_plane:
        return _run_vertical(
            cfg, design, doc, path_pts, run_dir, dxf_out, write_files
        )
    return _run_plan(
        cfg, design, doc, path_pts, carriageway, run_dir, dxf_out, write_files
    )


def _run_plan(
    cfg: ProjectConfig,
    design,
    doc,
    path_pts: list,
    carriageway,
    run_dir: Path,
    dxf_out: str | Path | None,
    write_files: bool,
) -> AnalysisResult:
    max_steer = cfg.turning.max_steer_angle_deg
    for a in design.axles:
        if a.is_steering and a.max_steer_angle_deg is not None:
            max_steer = min(max_steer, a.max_steer_angle_deg)
    speed_m_per_s = cfg.turning.design_speed_kmh / 3.6
    pts = densify_path(path_pts, cfg.simulation.densify_arcs_to).tolist()
    arts = getattr(design, "articulation_positions_m", None) or (
        [design.articulation_longitudinal_m]
        if getattr(design, "articulation_longitudinal_m", None) is not None
        else []
    )
    if arts:
        wheelbase_m = max(0.1, 0.0 - arts[0])
    else:
        rear_pos = min((a.longitudinal_pos for a in design.axles), default=-4.0)
        wheelbase_m = max(0.1, 0.0 - rear_pos)
    lookahead_m = max(3.0, 2.0 * cfg.simulation.step_size_m)
    lock_mode = "stop_lock ON" if cfg.turning.stop_lock.enabled else "stop_lock OFF"
    logger.info(
        "Path-follow: wheelbase=%.2fm lookahead=%.2fm step=%.2fm maxSteer=%.1f° %s",
        wheelbase_m,
        lookahead_m,
        cfg.simulation.step_size_m,
        max_steer,
        lock_mode,
    )

    positions, steer_hist, segment_poses = follow_path(
        pts,
        wheelbase_m=wheelbase_m,
        step_m=cfg.simulation.step_size_m,
        lookahead_m=lookahead_m,
        max_steer_deg=max_steer,
        stop_lock_enabled=cfg.turning.stop_lock.enabled,
        rate_of_turn_deg_per_s=cfg.turning.rate_of_turn_deg_per_s,
        speed_m_per_s=speed_m_per_s,
        pid_enabled=cfg.turning.pid.enabled,
        pid_kp=cfg.turning.pid.kp,
        pid_ki=cfg.turning.pid.ki,
        pid_kd=cfg.turning.pid.kd,
        path_recovery_gain=cfg.simulation.path_recovery_gain,
        vehicle=design,
    )
    if segment_poses and len(segment_poses) > 0:
        logger.info(
            "Articulated vehicle: %d segments, %d steps",
            len(segment_poses[0]),
            len(segment_poses),
        )

    max_steer_deg = max((abs(s) for s in steer_hist), default=0.0)
    min_radius = (
        wheelbase_m / math.tan(math.radians(max_steer_deg))
        if max_steer_deg > 1e-6
        else 0.0
    )

    env = None
    if positions:
        env = swept_envelope_polygon(
            positions, design, segment_poses=segment_poses
        )
    outer = _envelope_ring(env)
    if outer is None and positions:
        outer = [(float(p[0]), float(p[1])) for p in positions]

    clearance = ClearanceResult(0.0, 0.0, False, None)
    if env is not None and carriageway is not None:
        clearance = compute_clearance(env, carriageway)
    report_data: ReportData = build_report(
        design.name, max_steer_deg, min_radius, clearance
    )
    report_dict = {
        "vehicle_name": report_data.vehicle_name,
        "max_steer_angle_deg": report_data.max_steer_angle_deg,
        "min_radius_m": report_data.min_radius_m,
        "encroachment_area_m2": report_data.clearance.encroachment_area_m2,
        "max_penetration_m": report_data.clearance.max_penetration_m,
        "pass": report_data.pass_fail,
        "mode": "plan",
    }

    out_prefix = (
        Path(cfg.dxf.input_file).stem + "_" if cfg.dxf.input_file else "out_"
    )
    plot_path = anim_path = dxf_path = json_path = text_path = None
    cw_xy = list(carriageway.exterior.coords) if carriageway else None

    if write_files:
        if "text" in cfg.output.report:
            text_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}report.txt"
            write_text_report(report_data, text_path)
        if "json" in cfg.output.report:
            json_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}report.json"
            write_json_report(report_data, json_path)
        if cfg.output.dxf and doc and positions:
            from .dxf_io import write_swept_layers

            write_swept_layers(
                doc,
                cfg.output.dxf_prefix,
                outer or [],
                [],
                positions,
                None,
                vehicle=design,
                segment_poses=segment_poses,
            )
            if dxf_out:
                dxf_path = Path(dxf_out)
                if not dxf_path.is_absolute():
                    dxf_path = (Path.cwd() / dxf_path).resolve()
                dxf_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                dxf_path = (
                    run_dir
                    / f"{cfg.output.dxf_prefix}{Path(cfg.dxf.input_file).stem}_out.dxf"
                )
            doc.saveas(str(dxf_path))
            logger.info("Saved DXF: %s", dxf_path)
        if cfg.output.plot and path_pts and positions:
            plot_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}plot.png"
            save_plot(
                path_pts,
                positions,
                cw_xy,
                str(plot_path),
                vehicle=design,
                steer_angles=steer_hist,
                segment_poses=segment_poses,
            )
        if cfg.output.animation and path_pts and positions:
            anim_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}animation.gif"
            logger.info("Generating animation (%d frames)...", len(positions))
            save_animation(
                path_pts,
                positions,
                cw_xy,
                str(anim_path),
                vehicle=design,
                fps=cfg.output.animation_fps,
                steer_angles=steer_hist,
                segment_poses=segment_poses,
            )

    return AnalysisResult(
        ok=True,
        mode="plan",
        vehicle_name=design.name,
        report=report_dict,
        run_dir=run_dir,
        path_pts=[(float(x), float(y)) for x, y in path_pts],
        positions=list(positions) if positions else [],
        steer_angles_deg=list(steer_hist) if steer_hist else [],
        envelope_outer=outer,
        carriageway_xy=[(float(x), float(y)) for x, y in cw_xy] if cw_xy else None,
        plot_path=plot_path,
        animation_path=anim_path,
        dxf_path=dxf_path,
        report_json_path=json_path,
        report_text_path=text_path,
        message="Plan swept-path analysis complete",
        max_steer_deg=max_steer_deg,
        min_radius_m=min_radius,
        clearance=clearance,
    )


def _run_vertical(
    cfg: ProjectConfig,
    design,
    doc,
    path_pts: list,
    run_dir: Path,
    dxf_out: str | Path | None,
    write_files: bool,
) -> AnalysisResult:
    import numpy as np

    from .dxf_io import write_vertical_profile_dxf, write_vertical_swept_extent_dxf
    from .vehicle import VerticalProfile
    from .vertical_plot import (
        profile_swept_extent_polygon,
        save_vertical_animation,
        save_vertical_plot,
    )
    from .vertical_sim import simulate_vertical

    vp = design.vertical if design.vertical is not None else VerticalProfile()
    logger.info(
        "Vertical plane: steering path is (chainage m, elevation m)"
    )
    pts = densify_path(path_pts, cfg.simulation.densify_arcs_to).tolist()
    path = np.asarray(pts, dtype=float)
    frames, gmin, ok = simulate_vertical(
        path, design, vp, cfg.simulation.step_size_m
    )
    path_list = [(float(r[0]), float(r[1])) for r in pts]
    extent_ring = profile_swept_extent_polygon(frames, vp, design, path)
    report_dict = {
        "mode": "vertical_profile",
        "vehicle_name": design.name,
        "min_chord_ground_margin_m": float(gmin),
        "ground_clearance_required_m": float(vp.ground_clearance_m),
        "pass_clearance": bool(ok),
        "pass": bool(ok),
    }
    out_prefix = (
        Path(cfg.dxf.input_file).stem + "_" if cfg.dxf.input_file else "out_"
    )
    plot_path = anim_path = dxf_path = json_path = text_path = None

    if write_files:
        if "text" in cfg.output.report:
            text_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}report.txt"
            write_vertical_text_report(
                design.name, gmin, vp.ground_clearance_m, ok, text_path
            )
        if "json" in cfg.output.report:
            json_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}report.json"
            write_vertical_json_report(
                design.name, gmin, vp.ground_clearance_m, ok, json_path
            )
        if cfg.output.dxf:
            out_doc = doc
            if out_doc is None:
                try:
                    import ezdxf

                    out_doc = ezdxf.new("R2010")
                except ImportError:
                    out_doc = None
            if out_doc is not None:
                write_vertical_profile_dxf(
                    out_doc, path_list, cfg.output.dxf_prefix
                )
                if extent_ring:
                    write_vertical_swept_extent_dxf(
                        out_doc, extent_ring, cfg.output.dxf_prefix
                    )
                if dxf_out:
                    dxf_path = Path(dxf_out)
                    if not dxf_path.is_absolute():
                        dxf_path = (Path.cwd() / dxf_path).resolve()
                    dxf_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    dxf_path = (
                        run_dir
                        / f"{cfg.output.dxf_prefix}{Path(cfg.dxf.input_file).stem}_out.dxf"
                    )
                out_doc.saveas(str(dxf_path))
                logger.info("Saved DXF: %s", dxf_path)
        if cfg.output.plot and frames:
            plot_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}plot.png"
            save_vertical_plot(
                path_list, frames, plot_path, vp, design, path
            )
        if cfg.output.animation and frames:
            anim_path = run_dir / f"{cfg.output.dxf_prefix}{out_prefix}animation.gif"
            logger.info(
                "Writing vertical animation (%d frames) → %s", len(frames), anim_path
            )
            save_vertical_animation(
                path_list,
                frames,
                anim_path,
                vp,
                design,
                path,
                fps=cfg.output.animation_fps,
            )

    return AnalysisResult(
        ok=True,
        mode="vertical",
        vehicle_name=design.name,
        report=report_dict,
        run_dir=run_dir,
        path_pts=path_list,
        envelope_outer=extent_ring,
        plot_path=plot_path,
        animation_path=anim_path,
        dxf_path=dxf_path,
        report_json_path=json_path,
        report_text_path=text_path,
        message="Vertical profile analysis complete",
        clearance=ClearanceResult(0.0, 0.0, not ok, None),
    )
