"""Text and JSON report: max steer, min radius, clearances, pass/fail. See PDR §2."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .clearance import ClearanceResult

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    max_steer_angle_deg: float
    min_radius_m: float
    clearance: ClearanceResult
    pass_fail: bool
    vehicle_name: str


def build_report(vehicle_name: str, max_steer_deg: float, min_radius: float,
                 clearance: ClearanceResult) -> ReportData:
    pass_fail = not clearance.has_encroachment
    return ReportData(
        max_steer_angle_deg=max_steer_deg,
        min_radius_m=min_radius,
        clearance=clearance,
        pass_fail=pass_fail,
        vehicle_name=vehicle_name,
    )


def write_text_report(report: ReportData, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Vehicle: {report.vehicle_name}",
        f"Max steer angle (deg): {report.max_steer_angle_deg:.2f}",
        f"Min radius (m): {report.min_radius_m:.2f}",
        f"Encroachment area (m²): {report.clearance.encroachment_area_m2:.4f}",
        f"Max penetration (m): {report.clearance.max_penetration_m:.4f}",
        f"Pass: {report.pass_fail}",
    ]
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    logger.info("Wrote text report: %s", path)


def write_json_report(report: ReportData, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "vehicle_name": report.vehicle_name,
        "max_steer_angle_deg": report.max_steer_angle_deg,
        "min_radius_m": report.min_radius_m,
        "encroachment_area_m2": report.clearance.encroachment_area_m2,
        "max_penetration_m": report.clearance.max_penetration_m,
        "pass": report.pass_fail,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Wrote JSON report: %s", path)


def write_vertical_text_report(
    vehicle_name: str,
    min_chord_ground_margin_m: float,
    ground_clearance_required_m: float,
    pass_clearance: bool,
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Vehicle: {vehicle_name}",
        f"Mode: vertical profile (chainage vs elevation)",
        f"Min chord–terrain margin (m): {min_chord_ground_margin_m:.4f}",
        f"Required ground clearance (m): {ground_clearance_required_m:.4f}",
        f"Pass clearance: {pass_clearance}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote vertical text report: %s", path)


def write_vertical_json_report(
    vehicle_name: str,
    min_chord_ground_margin_m: float,
    ground_clearance_required_m: float,
    pass_clearance: bool,
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "mode": "vertical_profile",
        "vehicle_name": vehicle_name,
        "min_chord_ground_margin_m": min_chord_ground_margin_m,
        "ground_clearance_required_m": ground_clearance_required_m,
        "pass_clearance": pass_clearance,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Wrote vertical JSON report: %s", path)
