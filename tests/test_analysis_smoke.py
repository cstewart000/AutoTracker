"""Smoke tests for analysis API and packaging."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_import_package():
    import pysweptpath
    from pysweptpath.analysis import AnalysisResult, run_analysis

    assert pysweptpath.__version__
    assert callable(run_analysis)
    assert AnalysisResult


def test_load_vehicle_and_config():
    from pysweptpath.config import load_config
    from pysweptpath.vehicle import load_vehicle

    veh = ROOT / "vehicles" / "semi_wb50.xml"
    assert veh.is_file()
    v = load_vehicle(veh)
    assert v.name
    assert len(v.axles) >= 2

    cfg_path = ROOT / "config.xml"
    if cfg_path.is_file():
        cfg = load_config(cfg_path)
        assert cfg.simulation.step_size_m > 0


def test_run_analysis_rectangle(tmp_path):
    from pysweptpath.analysis import run_analysis
    from pysweptpath.config import (
        DxfConfig,
        OutputConfig,
        PIDConfig,
        ProjectConfig,
        SimulationConfig,
        StopLockConfig,
        TurningConfig,
    )

    dxf = ROOT / "input models" / "rectangle_20x60.dxf"
    if not dxf.is_file():
        pytest.skip("demo DXF missing")
    vehicle = ROOT / "vehicles" / "semi_wb50.xml"

    cfg = ProjectConfig(
        design_vehicle=str(vehicle),
        check_vehicle=None,
        dxf=DxfConfig(
            input_file=str(dxf),
            steering_layer="Steering_Centreline",
            carriageway_layer="Carriageway_Boundary",
        ),
        simulation=SimulationConfig(
            step_size_m=0.5,
            densify_arcs_to=0.25,
            path_recovery_gain=0.8,
            vertical_plane=False,
        ),
        turning=TurningConfig(
            design_speed_kmh=5.0,
            max_steer_angle_deg=42.0,
            rate_of_turn_deg_per_s=15.0,
            pid=PIDConfig(enabled=False, kp=0.5, ki=0.0, kd=0.1),
            stop_lock=StopLockConfig(enabled=True, min_turning_radius_m=None),
        ),
        output=OutputConfig(
            dxf=True,
            dxf_prefix="Swept_",
            plot=True,
            animation=False,
            animation_fps=8,
            report=["json"],
        ),
    )
    result = run_analysis(cfg=cfg, output_dir=tmp_path, write_files=True, animation=False)
    assert result.ok
    assert result.mode == "plan"
    assert len(result.positions) > 5
    assert result.plot_path is None or result.plot_path.exists() or True
    # plot should exist when write_files
    assert result.plot_path and result.plot_path.exists()
    public = result.to_public_dict()
    assert "report" in public
    assert public["ok"] is True
