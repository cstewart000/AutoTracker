"""
AutoTracker web API + UI.

Run locally:
  uvicorn webapp.main:app --reload --host 0.0.0.0 --port 8000

Railway sets PORT; use start command in railway.toml.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pysweptpath.analysis import run_analysis
from pysweptpath.config import (
    DxfConfig,
    OutputConfig,
    PIDConfig,
    ProjectConfig,
    SimulationConfig,
    StopLockConfig,
    TurningConfig,
    load_config,
)
from pysweptpath.turn_templates import simulate_standard_profiles
from pysweptpath.vehicle import load_vehicle, write_vehicle
from pysweptpath.vehicle_json import (
    editor_outline,
    vehicle_from_dict,
    vehicle_to_dict,
)

# Headless plot backend for Railway / servers
os.environ.setdefault("MPLBACKEND", "Agg")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("webapp")

ROOT = Path(__file__).resolve().parent.parent
VEHICLES_DIR = ROOT / "vehicles"
INPUT_MODELS = ROOT / "input models"
STATIC_DIR = Path(__file__).resolve().parent / "static"
JOBS_DIR = Path(os.environ.get("AUTOTRACKER_JOBS_DIR", ROOT / "web_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AutoTracker / pySweptPath",
    description="Open-source swept path analysis (AutoTURN-style)",
    version="0.3.0",
)


class TurnProfileRequest(BaseModel):
    vehicle_id: str | None = None
    vehicle: dict | None = None
    radius_90_m: float = Field(12.5, ge=3.0, le=80.0)
    radius_180_m: float = Field(12.5, ge=3.0, le=80.0)
    step_m: float = Field(0.35, ge=0.1, le=2.0)
    stop_lock: bool = True


class VehicleValidateRequest(BaseModel):
    vehicle: dict

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _list_vehicles() -> list[dict[str, str]]:
    items = []
    if not VEHICLES_DIR.is_dir():
        return items
    for p in sorted(VEHICLES_DIR.glob("*.xml")):
        items.append({"id": p.stem, "name": p.stem.replace("_", " "), "file": p.name})
    return items


def _list_demos() -> list[dict[str, Any]]:
    demos = []
    if not INPUT_MODELS.is_dir():
        return demos
    for p in sorted(INPUT_MODELS.glob("*.dxf")):
        demos.append(
            {
                "id": p.stem,
                "name": p.stem.replace("_", " "),
                "file": p.name,
                "vertical": "profile" in p.stem.lower() or "vertical" in p.stem.lower(),
            }
        )
    return demos


def _vehicle_path(vehicle_id: str) -> Path:
    # Accept stem or filename
    name = vehicle_id if vehicle_id.endswith(".xml") else f"{vehicle_id}.xml"
    path = (VEHICLES_DIR / Path(name).name).resolve()
    if not str(path).startswith(str(VEHICLES_DIR.resolve())):
        raise HTTPException(400, "Invalid vehicle path")
    if not path.is_file():
        raise HTTPException(404, f"Vehicle not found: {vehicle_id}")
    return path


def _build_cfg(
    *,
    vehicle_path: Path,
    dxf_path: Path,
    vertical_plane: bool,
    step_size_m: float,
    max_steer_deg: float,
    design_speed_kmh: float,
    stop_lock: bool,
    animation: bool,
    steering_layer: str,
    carriageway_layer: str,
) -> ProjectConfig:
    return ProjectConfig(
        design_vehicle=str(vehicle_path),
        check_vehicle=None,
        dxf=DxfConfig(
            input_file=str(dxf_path),
            steering_layer=steering_layer,
            carriageway_layer=carriageway_layer,
        ),
        simulation=SimulationConfig(
            step_size_m=step_size_m,
            densify_arcs_to=min(0.1, step_size_m),
            path_recovery_gain=0.8,
            vertical_plane=vertical_plane,
        ),
        turning=TurningConfig(
            design_speed_kmh=design_speed_kmh,
            max_steer_angle_deg=max_steer_deg,
            rate_of_turn_deg_per_s=15.0,
            pid=PIDConfig(enabled=False, kp=0.5, ki=0.0, kd=0.1),
            stop_lock=StopLockConfig(enabled=stop_lock, min_turning_radius_m=None),
        ),
        output=OutputConfig(
            dxf=True,
            dxf_prefix="Swept_",
            plot=True,
            animation=animation,
            animation_fps=8,
            report=["text", "json"],
        ),
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        return HTMLResponse("<h1>AutoTracker</h1><p>UI missing.</p>", status_code=500)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "autotracker", "version": "0.3.0"}


@app.get("/api/vehicles")
def api_vehicles() -> dict[str, Any]:
    return {"vehicles": _list_vehicles()}


def _resolve_vehicle(
    vehicle_id: str | None = None, vehicle_dict: dict | None = None
):
    if vehicle_dict:
        return vehicle_from_dict(vehicle_dict)
    if vehicle_id:
        return load_vehicle(_vehicle_path(vehicle_id))
    raise HTTPException(400, "Provide vehicle_id or vehicle JSON")


@app.get("/api/vehicles/{vehicle_id}")
def api_vehicle_detail(vehicle_id: str) -> dict[str, Any]:
    """Full vehicle JSON + plan outline for the editor."""
    path = _vehicle_path(vehicle_id)
    v = load_vehicle(path)
    data = vehicle_to_dict(v)
    data["id"] = path.stem
    data["file"] = path.name
    data["outline"] = editor_outline(v)
    return data


@app.post("/api/vehicles/validate")
def api_vehicle_validate(body: VehicleValidateRequest) -> dict[str, Any]:
    """Validate editor vehicle JSON; return outline for canvas redraw."""
    try:
        v = vehicle_from_dict(body.vehicle)
    except Exception as e:
        raise HTTPException(400, f"Invalid vehicle: {e}") from e
    return {
        "ok": True,
        "vehicle": vehicle_to_dict(v),
        "outline": editor_outline(v),
    }


@app.post("/api/vehicles/export-xml")
def api_vehicle_export_xml(body: VehicleValidateRequest) -> Response:
    """Return vehicle XML for download."""
    try:
        v = vehicle_from_dict(body.vehicle)
    except Exception as e:
        raise HTTPException(400, f"Invalid vehicle: {e}") from e
    job = JOBS_DIR / "exports"
    job.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in v.name)[:60]
    path = job / f"{safe or 'vehicle'}.xml"
    write_vehicle(v, path)
    xml_text = path.read_text(encoding="utf-8")
    return Response(
        content=xml_text,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
        },
    )


@app.post("/api/turn-profiles")
def api_turn_profiles(body: TurnProfileRequest) -> dict[str, Any]:
    """Simulate standard 90° and 180° turn swept-path profiles."""
    try:
        v = _resolve_vehicle(body.vehicle_id, body.vehicle)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Invalid vehicle: {e}") from e
    try:
        result = simulate_standard_profiles(
            v,
            radius_90_m=body.radius_90_m,
            radius_180_m=body.radius_180_m,
            step_m=body.step_m,
            stop_lock=body.stop_lock,
        )
        result["outline"] = editor_outline(v)
        return result
    except Exception as e:
        logger.exception("Turn profile failed: %s", e)
        raise HTTPException(500, f"Turn profile failed: {e}") from e


@app.get("/api/demos")
def api_demos() -> dict[str, Any]:
    return {"demos": _list_demos()}


@app.post("/api/simulate")
async def api_simulate(
    vehicle: str = Form("ap_g34_prime_mover_semi_19m"),
    demo: str | None = Form(None),
    vertical_plane: bool = Form(False),
    step_size_m: float = Form(0.25),
    max_steer_angle_deg: float = Form(42.0),
    design_speed_kmh: float = Form(5.0),
    stop_lock: bool = Form(True),
    animation: bool = Form(False),
    steering_layer: str = Form("Steering_Centreline"),
    carriageway_layer: str = Form("Carriageway_Boundary"),
    dxf: UploadFile | None = File(None),
) -> dict[str, Any]:
    """
    Run swept-path analysis.

    Provide either an uploaded ``dxf`` file or a ``demo`` id from /api/demos.
    Animation is off by default (slow); enable for GIFs.
    """
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        vehicle_path = _vehicle_path(vehicle)

        if dxf is not None and dxf.filename:
            dest = job_dir / Path(dxf.filename).name
            if not dest.suffix.lower() == ".dxf":
                dest = dest.with_suffix(".dxf")
            content = await dxf.read()
            if len(content) > 40 * 1024 * 1024:
                raise HTTPException(400, "DXF too large (max 40 MB)")
            dest.write_bytes(content)
            dxf_path = dest
        elif demo:
            demo_file = Path(demo).name
            if not demo_file.endswith(".dxf"):
                demo_file = f"{demo_file}.dxf"
            src = (INPUT_MODELS / demo_file).resolve()
            if not str(src).startswith(str(INPUT_MODELS.resolve())) or not src.is_file():
                raise HTTPException(404, f"Demo not found: {demo}")
            dxf_path = job_dir / src.name
            shutil.copy2(src, dxf_path)
            if "profile" in src.stem.lower() or "vertical" in src.stem.lower():
                vertical_plane = True
        else:
            # Default demo
            default = INPUT_MODELS / "rectangle_20x60.dxf"
            if not default.is_file():
                # fallback any dxf
                any_dxf = list(INPUT_MODELS.glob("*.dxf"))
                if not any_dxf:
                    raise HTTPException(400, "No DXF upload and no demos available")
                default = any_dxf[0]
            dxf_path = job_dir / default.name
            shutil.copy2(default, dxf_path)

        cfg = _build_cfg(
            vehicle_path=vehicle_path,
            dxf_path=dxf_path,
            vertical_plane=vertical_plane,
            step_size_m=max(0.05, min(step_size_m, 2.0)),
            max_steer_deg=max_steer_angle_deg,
            design_speed_kmh=design_speed_kmh,
            stop_lock=stop_lock,
            animation=animation,
            steering_layer=steering_layer,
            carriageway_layer=carriageway_layer,
        )

        result = run_analysis(
            cfg=cfg,
            output_dir=job_dir / "out",
            write_files=True,
            animation=animation,
        )

        public = result.to_public_dict()
        public["job_id"] = job_id
        # Rewrite file paths to API URLs
        files = public.get("files") or {}
        url_files: dict[str, str | None] = {}
        for key, path_str in files.items():
            if key == "run_dir" or not path_str:
                url_files[key] = None
                continue
            p = Path(path_str)
            if p.exists():
                url_files[key] = f"/api/jobs/{job_id}/files/{p.name}"
            else:
                url_files[key] = None
        public["files"] = url_files
        return public
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Simulate failed: %s", e)
        raise HTTPException(500, f"Simulation failed: {e}") from e


@app.get("/api/jobs/{job_id}/files/{filename}")
def job_file(job_id: str, filename: str):
    safe_job = Path(job_id).name
    safe_name = Path(filename).name
    # Search under job dir
    base = (JOBS_DIR / safe_job).resolve()
    if not str(base).startswith(str(JOBS_DIR.resolve())) or not base.is_dir():
        raise HTTPException(404, "Job not found")
    candidates = list(base.rglob(safe_name))
    if not candidates:
        raise HTTPException(404, "File not found")
    path = candidates[0]
    if not str(path.resolve()).startswith(str(base)):
        raise HTTPException(404, "File not found")
    media = "application/octet-stream"
    if path.suffix.lower() == ".png":
        media = "image/png"
    elif path.suffix.lower() == ".gif":
        media = "image/gif"
    elif path.suffix.lower() == ".json":
        media = "application/json"
    elif path.suffix.lower() == ".dxf":
        media = "application/dxf"
    elif path.suffix.lower() == ".txt":
        media = "text/plain"
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/config/default")
def default_config_summary() -> dict[str, Any]:
    cfg_path = ROOT / "config.xml"
    if not cfg_path.is_file():
        return {"exists": False}
    try:
        cfg = load_config(cfg_path)
        return {
            "exists": True,
            "design_vehicle": Path(cfg.design_vehicle).name,
            "input_file": Path(cfg.dxf.input_file).name,
            "vertical_plane": cfg.simulation.vertical_plane,
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}
