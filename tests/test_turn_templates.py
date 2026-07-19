"""Turn templates and vehicle JSON."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_vehicle_json_roundtrip():
    from pysweptpath.vehicle import load_vehicle
    from pysweptpath.vehicle_json import vehicle_from_dict, vehicle_to_dict

    path = ROOT / "vehicles" / "semi_wb50.xml"
    v = load_vehicle(path)
    d = vehicle_to_dict(v)
    v2 = vehicle_from_dict(d)
    assert v2.name == v.name
    assert len(v2.axles) == len(v.axles)
    assert abs(v2.axles[0].longitudinal_pos - v.axles[0].longitudinal_pos) < 1e-9


def test_90_180_paths():
    from pysweptpath.turn_templates import make_180_degree_path, make_90_degree_path

    p90 = make_90_degree_path(12.5, approach_m=10, exit_m=10, step_m=1.0)
    assert len(p90) > 10
    # Ends roughly north of start for left turn
    assert p90[-1][1] > 5

    p180 = make_180_degree_path(12.5, approach_m=10, exit_m=10, step_m=1.0)
    assert len(p180) > 15
    # U-turn ends with similar x to start of arc region, y ≈ 2R
    assert abs(p180[-1][1] - 25.0) < 3.0


def test_simulate_profiles():
    from pysweptpath.turn_templates import simulate_standard_profiles
    from pysweptpath.vehicle import load_vehicle

    v = load_vehicle(ROOT / "vehicles" / "semi_wb50.xml")
    out = simulate_standard_profiles(v, radius_90_m=15.0, radius_180_m=15.0, step_m=0.5)
    assert "90" in out["profiles"] and "180" in out["profiles"]
    assert out["profiles"]["90"]["envelope"] is not None or out["profiles"]["90"]["steps"] > 0
    assert out["profiles"]["90"]["max_steer_deg"] >= 0
