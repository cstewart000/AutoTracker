# AutoTracker / pySweptPath

Open-source **swept path analysis** (AutoTURN-style) in pure Python for road and site design. Read a steering path and carriageway from DXF, simulate design vehicles with Ackermann kinematics, output swept envelopes and clearance reports.

**Front ends:** CLI · optional Tkinter vehicle editor · **web app** (FastAPI)

Planned work lives in [`PLANNED_FEATURES.md`](PLANNED_FEATURES.md).

## Goals

- Read steering path (polyline) and carriageway boundary (hatch) from DXF
- Accurate low-speed Ackermann steering kinematics
- Design vehicles (XML + optional Tkinter editor; Austroads AP-G34 library)
- Dual-vehicle checking (design + check vehicle)
- Swept envelopes, wheel tracks, clearance reporting
- Programmatic `run_analysis()` API shared by CLI and web
- MIT license, minimal dependencies, scriptable

## Requirements

- Python 3.10 – 3.12
- See `requirements.txt` / `pyproject.toml`

## Install

```bash
cd AutoTracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional editable install:
# pip install -e ".[dev]"
```

## Usage

### CLI

```bash
python -m pysweptpath.cli --config config.xml
python -m pysweptpath.cli --config config.xml --dxf-out output.dxf --no-animation
python -m pysweptpath.editor.app   # vehicle editor
```

### Web app (local)

```bash
export MPLBACKEND=Agg
uvicorn webapp.main:app --host 0.0.0.0 --port 8000
# open http://127.0.0.1:8000
```

**Web tabs:** Analyze (DXF sim) · **Vehicle editor** (drag axles / body / articulation) · **90° / 180° turn profiles**

API: `GET /api/health`, `GET /api/vehicles`, `GET /api/vehicles/{id}`, `POST /api/vehicles/validate`, `POST /api/vehicles/export-xml`, `POST /api/turn-profiles`, `GET /api/demos`, `POST /api/simulate`, OpenAPI at `/docs`.

### Programmatic API

```python
from pysweptpath.analysis import run_analysis

result = run_analysis("config.xml", animation=False)
print(result.report, result.plot_path)
```

### Deploy (Railway)

Configured via `railway.toml` / `Procfile`. Start command:

```text
uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
```


## How to see output

Run the CLI from the project root (next to `config.xml`). Each run writes under **`reports/<input_dxf_stem>/<design_vehicle_stem>/`** (next to `config.xml`), where stems come from the input DXF filename and the design vehicle XML filename. **`--dxf-out`** still accepts an explicit path for the output DXF only.

| Output | When | File(s) |
|--------|------|--------|
| **Text report** | `output/report` includes `text` in config | `reports/.../Swept_<input_stem>_report.txt` |
| **JSON report** | `output/report` includes `json` | `reports/.../Swept_<input_stem>_report.json` |
| **DXF** | `output/dxf` is true and input DXF exists | `reports/.../Swept_<input_stem>_out.dxf` (or `--dxf-out path`) |
| **Plot** | `output/plot` is true | `reports/.../Swept_<input_stem>_plot.png` |
| **Animation** | `output/animation` is true | `reports/.../Swept_<input_stem>_animation.gif` |

To use the included demo, set `dxf/input_file` to `demo.dxf` in `config.xml`, then run the CLI from the project root.

**Examples** (with `demo.dxf` as input and vehicle `tiny_home_12m_trailer.xml`):

- Open **`reports/demo/tiny_home_12m_trailer/Swept_demo_plot.png`** in an image viewer to see the steering path and swept centreline.
- Open **`reports/demo/tiny_home_12m_trailer/Swept_demo_out.dxf`** in a DXF viewer (e.g. LibreCAD, AutoCAD, QCAD) to see layers: swept outer, steering path, carriageway.
- Read **`reports/demo/tiny_home_12m_trailer/Swept_demo_report.txt`** or **`..._report.json`** for max steer angle, min radius, clearance, pass/fail.

## Project layout

```
AutoTracker/
├── README.md
├── pdr.md              # Product requirements
├── requirements.txt
├── config.xml          # Example project config
├── input models/       # Input DXF files
├── reports/            # CLI outputs (per input DXF + vehicle)
├── pysweptpath/        # Main package
│   ├── cli.py          # Command-line interface
│   ├── config.py       # config.xml loader
│   ├── vehicle.py      # Vehicle XML + dataclass
│   ├── kinematics.py   # Ackermann simulator
│   ├── dxf_io.py       # DXF read/write
│   ├── clearance.py    # Encroachment & clearance
│   ├── report.py       # Text/JSON report
│   └── editor/         # Tkinter vehicle editor
├── vehicles/           # Design vehicle XML files
└── tests/
```

## Configuration

Edit `config.xml` to set:

- `vehicles/design_vehicle`, optional `check_vehicle`
- `dxf/input_file`, `steering_layer`, `carriageway_layer`
- `simulation/vertical_plane` — when `true`, the steering path is **(chainage m, elevation m)**; plots and DXF use **chainage left → right** and **elevation up**; each **body segment** is drawn **rotated** with the chord through its axles, **split at articulations**; outputs include **swept profile extent** and an **animation** when `output/animation` is `true` (see `config.profile_vertical_demo.xml` + `input models/profile_demo_vertical.dxf`)
- `simulation/step_size_m`, `densify_arcs_to`
- `turning/design_speed_kmh`, `stop_lock` (full_lock / limited)
- `output/dxf`, `plot`, `report` (text, json)

## Vehicle XML

Vehicles are defined in XML under `vehicles/`. See `pdr.md` §3.1 for the schema (body, axles, polygon, steering axle, track width, max steer angle). Optional **`vertical_profile`** (used when `vertical_plane` is true): `wheel_radius_m`, `ground_clearance_m`, `body_depth_m`, `trailer_tangent_window_m` (secant half-width at the trailer’s central axle for smooth pitch).

### Austroads AP-G34 design vehicles

The `vehicles/` folder includes standard design vehicles from **Austroads AP-G34-23** (Design Vehicles and Turning Path Templates):

| Vehicle | File | Length |
|--------|------|--------|
| Passenger vehicle | `ap_g34_passenger_5_2m.xml` | 5.2 m |
| Passenger car + trailer | `ap_g34_passenger_car_trailer_17_6m.xml` | 17.6 m |
| Service vehicle | `ap_g34_service_vehicle_8_8m.xml` | 8.8 m |
| Single unit truck/bus | `ap_g34_single_unit_truck_12_5m.xml` | 12.5 m |
| Long rigid bus | `ap_g34_long_rigid_bus_14_5m.xml` | 14.5 m |
| Articulated bus | `ap_g34_articulated_bus_19m.xml` | 19 m |
| Prime mover + semi-trailer | `ap_g34_prime_mover_semi_19m.xml` | 19 m |
| Prime mover + long semi | `ap_g34_prime_mover_long_semi_25m.xml` | 25 m |
| B-double | `ap_g34_b_double_26m.xml` | 26 m |
| B-triple | `ap_g34_b_triple_35_4m.xml` | 35.4 m |
| A-double (road train) | `ap_g34_a_double_36_2m.xml` | 36.2 m |
| A-triple (road train) | `ap_g34_a_triple_53_4m.xml` | 53.4 m |

Set `vehicles/design_vehicle` in `config.xml` to e.g. `vehicles/ap_g34_prime_mover_semi_19m.xml` to use an AP-G34 vehicle.

## License

MIT.
