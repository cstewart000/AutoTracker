# AutoTracker / pySweptPath — Planned Features & Actions

Living backlog derived from product discussion (2026-07). Check items as they ship.

---

## Phase A — Foundations (in progress / ship first)

| ID | Item | Status | Notes |
|----|------|--------|--------|
| A1 | Extract `run_analysis()` + structured `AnalysisResult` | ✅ | `pysweptpath/analysis.py` |
| A2 | Git repository + GitHub remote | ✅ | This repo |
| A3 | `pyproject.toml` installable package | ✅ | + `requirements.txt` |
| A4 | Automated tests (smoke + acceptance hooks) | ✅ | `tests/test_analysis_smoke.py` |
| A5 | Verified install / deps | ✅ | fastapi stack included |
| A6 | Document kinematics limits | ⬜ | Low-speed Ackermann only; no slip / reverse |
| A7 | Update PRD vs reality | ⬜ | Articulated + vertical plane already exist |
| A8 | Unify product naming (AutoTracker vs pySweptPath) | ⬜ | |

## Phase B — Web application

| ID | Item | Status | Notes |
|----|------|--------|--------|
| B1 | FastAPI job API (`/api/simulate`, vehicles, demos) | ✅ | `webapp/main.py` |
| B2 | Browser UI: upload DXF, pick vehicle, params | ✅ | `webapp/static/` |
| B3 | View plot + JSON report in page | ✅ | + canvas envelope preview |
| B4 | Download DXF / report / plot | ✅ | `/api/jobs/.../files/` |
| B5 | Railway deploy | ✅ | `railway.toml` |
| B6 | Interactive path editor (draw centreline) | ⬜ | |
| B7 | Vehicle preview (plan outline) | ✅ | Editor canvas + outline API |
| B8 | Frame scrubber (scrub along path) | ⬜ | Replace slow GIFs for review |
| B9 | Layer toggles (envelope, wheels, encroachment) | ⬜ | |
| B10 | Project sessions (localStorage / server) | ⬜ | |
| B11 | Web vehicle editor (drag-and-drop config) | ✅ | Axles, body, articulation |
| B12 | Standard 90° / 180° turn profile views | ✅ | `/api/turn-profiles` |

## Phase C — Accuracy & trust

| ID | Item | Status | Notes |
|----|------|--------|--------|
| C1 | Validation suite vs known turning templates | ⬜ | Austroads / simple radii |
| C2 | AutoTURN envelope comparison (~50 mm goal) | ⬜ | PDR acceptance |
| C3 | Stop-lock / full-lock reporting at chainage | ⬜ | “Failed at ch X, steer Y°” |
| C4 | Carriageway clearance UX (pass/fail map) | ⬜ | Wire `compute_clearance` end-to-end |
| C5 | Dual-vehicle checking (design + check) | ⬜ | Config field exists; pipeline partial |

## Phase D — Engineering features

| ID | Item | Status | Notes |
|----|------|--------|--------|
| D1 | Reverse manoeuvres | ⬜ | Docks, cul-de-sacs |
| D2 | Harden multi-unit coupling model + docs | ⬜ | Artic already in code |
| D3 | Plan + vertical in one project | ⬜ | |
| D4 | Clean Civil 3D / AutoCAD export layers | ⬜ | |
| D5 | Speed-based turning radius | ⬜ | |
| D6 | QGIS / Civil 3D plugin | ⬜ | Later |
| D7 | AutoTURN vehicle import (`.veh` / XML) | ⬜ | |
| D8 | Sample gallery (“click to run” demos) | ✅ | Demo dropdown from `input models/` |

## Phase E — Product polish

| ID | Item | Status | Notes |
|----|------|--------|--------|
| E1 | Keep CLI as power-user front door | ✅ | Web is additive |
| E2 | HTML/PDF report export | ⬜ | |
| E3 | Streamlit / DearPyGui interactive sim | ⬜ | PDR Phase 2 alternative |
| E4 | MIT license file if missing | ⬜ | |

---

## Implementation sequence (working order)

1. **A1** `run_analysis` + Result  
2. **A3–A5** packaging, deps, smoke tests  
3. **B1–B4** FastAPI + minimal UI  
4. **A2 + B5** GitHub + Railway  
5. Then C4, B6–B8, D1 as priority allows  

Update this file when shipping features (flip ⬜ → ✅ and note PR/commit).
