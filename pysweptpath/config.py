"""Project config.xml loader. See PDR §3.2."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DxfConfig:
    input_file: str
    steering_layer: str
    carriageway_layer: str


@dataclass
class SimulationConfig:
    step_size_m: float
    densify_arcs_to: float
    path_recovery_gain: float  # shrink lookahead when steering node deviates (0=off)
    vertical_plane: bool  # True: path is (chainage, elevation); vertical clearance sim


@dataclass
class StopLockConfig:
    enabled: bool  # true = vehicle can stop to maneuver
    min_turning_radius_m: float | None


@dataclass
class PIDConfig:
    enabled: bool
    kp: float  # Proportional gain
    ki: float  # Integral gain
    kd: float  # Derivative gain


@dataclass
class TurningConfig:
    design_speed_kmh: float
    max_steer_angle_deg: float  # Maximum steering angle limit
    rate_of_turn_deg_per_s: float  # Steering rate limit when moving (stop_lock off)
    pid: PIDConfig  # PID control for path tracking
    stop_lock: StopLockConfig


@dataclass
class OutputConfig:
    dxf: bool
    dxf_prefix: str
    plot: bool
    animation: bool
    animation_fps: int
    report: list[str]  # ["text", "json"]


@dataclass
class ProjectConfig:
    design_vehicle: str
    check_vehicle: str | None
    dxf: DxfConfig
    simulation: SimulationConfig
    turning: TurningConfig
    output: OutputConfig


def _text(elem: ET.Element | None, default: str = "") -> str:
    return (elem.text or "").strip() if elem is not None else default


def _bool(elem: ET.Element | None, default: bool = False) -> bool:
    t = _text(elem, "").lower()
    return t in ("true", "1", "yes") if t else default


def _float(elem: ET.Element | None, default: float = 0.0) -> float:
    if elem is None or not elem.text:
        return default
    try:
        return float(elem.text.strip())
    except ValueError:
        return default


def load_config(path: str | Path) -> ProjectConfig:
    path = Path(path)
    logger.info("Loading config from %s", path)
    tree = ET.parse(path)
    root = tree.getroot()
    base = path.parent

    v = root.find("vehicles")
    design = _text(v.find("design_vehicle"), "vehicles/semi_wb50.xml")
    check = v.find("check_vehicle")
    check_vehicle = _text(check) or None if check is not None else None

    dxf_el = root.find("dxf")
    dxf = DxfConfig(
        input_file=_text(dxf_el.find("input_file"), "input models/site_layout.dxf"),
        steering_layer=_text(dxf_el.find("steering_layer"), "Steering_Centreline"),
        carriageway_layer=_text(dxf_el.find("carriageway_layer"), "Carriageway_Boundary"),
    )
    if not (base / dxf.input_file).is_absolute() and (base / dxf.input_file).exists():
        dxf.input_file = str(base / dxf.input_file)

    sim = root.find("simulation")
    simulation = SimulationConfig(
        step_size_m=_float(sim.find("step_size_m"), 0.2),
        densify_arcs_to=_float(sim.find("densify_arcs_to"), 0.1),
        path_recovery_gain=_float(sim.find("path_recovery_gain"), 0.8),
        vertical_plane=_bool(sim.find("vertical_plane"), False) if sim is not None else False,
    )

    turn = root.find("turning")
    sl = turn.find("stop_lock") if turn is not None else None
    stop_lock = StopLockConfig(
        enabled=_bool(sl.find("enabled"), True) if sl is not None else True,
        min_turning_radius_m=_float(sl.find("min_turning_radius_m")) if sl is not None else None,
    )
    pid_el = turn.find("pid") if turn is not None else None
    pid = PIDConfig(
        enabled=_bool(pid_el.find("enabled"), False) if pid_el is not None else False,
        kp=_float(pid_el.find("kp"), 0.5) if pid_el is not None else 0.5,
        ki=_float(pid_el.find("ki"), 0.0) if pid_el is not None else 0.0,
        kd=_float(pid_el.find("kd"), 0.1) if pid_el is not None else 0.1,
    )
    turning = TurningConfig(
        design_speed_kmh=_float(turn.find("design_speed_kmh"), 5.0) if turn else 5.0,
        max_steer_angle_deg=_float(turn.find("max_steer_angle_deg"), 45.0) if turn else 45.0,
        rate_of_turn_deg_per_s=_float(turn.find("rate_of_turn_deg_per_s"), 15.0) if turn else 15.0,
        pid=pid,
        stop_lock=stop_lock,
    )

    out = root.find("output")
    report_str = _text(out.find("report"), "text,json")
    output = OutputConfig(
        dxf=_bool(out.find("dxf"), True),
        dxf_prefix=_text(out.find("dxf_prefix"), "Swept_"),
        plot=_bool(out.find("plot"), True),
        animation=_bool(out.find("animation"), False),
        animation_fps=int(_float(out.find("animation_fps"), 10)),
        report=[s.strip() for s in report_str.split(",") if s.strip()],
    )
    return ProjectConfig(
        design_vehicle=str(base / design) if design and not Path(design).is_absolute() else design,
        check_vehicle=str(base / check_vehicle) if check_vehicle and not Path(check_vehicle).is_absolute() else check_vehicle,
        dxf=dxf,
        simulation=simulation,
        turning=turning,
        output=output,
    )
