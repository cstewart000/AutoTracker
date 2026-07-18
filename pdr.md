Here is the **complete and consolidated Product Requirements Document (PRD)** for the open-source Python swept path analysis tool, incorporating all requirements discussed so far (as of February 2026).

**Product Requirements Document (PRD)**  
**Project Name:** pySweptPath – Open-Source Ackermann Swept Path Simulator  
**Version:** 1.1 (Consolidated – February 2026)  
**Status:** Detailed specification ready for implementation  
**Target audience:** Road geometrics / civil / transportation engineers, logistics planners, students, consultants who want to avoid commercial swept-path licences  

### 1. Overview & Business Objectives

Create the most practical **open-source** swept path analysis tool possible in pure Python with minimal dependencies, focused on real-world road and site design checks.

**Core goals**

- Read steering path (polyline) and carriageway boundary (hatch) from DXF  
- Support accurate low-speed Ackermann steering kinematics  
- Allow easy definition and visual editing of design vehicles  
- Provide dual-vehicle checking (design vehicle + check / critical vehicle)  
- Produce industry-acceptable swept envelopes, wheel tracks and clearance reporting  
- Remain 100 % open-source (MIT license), dependency-light, and scriptable  

**Non-goals (explicitly deferred to future major versions)**

- Articulated / multi-unit / low-loader combinations  
- Reverse manoeuvres  
- 3D vertical clearance & swept volume  
- Real-time interactive GUI for simulation (animation / drag path)  
- Integration into QGIS / FreeCAD / Civil 3D (possible via plugins later)

### 2. Functional Requirements – Summary Table

| Area                        | Must Have (MVP)                                                                 | Should Have (still Phase 1)                                 | Nice to Have (Phase 2+)                          |
|-----------------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------|--------------------------------------------------|
| Input – DXF                 | LWPOLYLINE / POLYLINE steering path + closed HATCH carriageway                  | Arcs (bulges), splines auto-flattened, coordinate scaling factor    | Multi-layout support, Xrefs                      |
| Vehicle definition          | XML file format, multiple axles, irregular body polygon                          | Visual vehicle editor (Tkinter Canvas)                              | Import from AutoTURN .veh / .xml                 |
| Kinematics                  | Incremental bicycle model + explicit Ackermann angles (inner & outer wheel)     | Steering angle limit & full-lock warning                            | Dynamic speed profile, slip angle                |
| Dual vehicle checking       | Design vehicle + optional larger check vehicle                                   | Separate swept areas and clearance reports                          | Different speeds per vehicle                     |
| Swept path generation       | Union of transformed body polygons → outer/inner envelopes                      | Wheel tracking lines (especially steered axle)                      | Offset curves, conflict highlighting             |
| Clearance analysis          | Encroachment polygon, area (m²), max penetration depth                           | Minimum lateral clearance when no encroachment                      | ISO 3864-style colour coding                     |
| Output – DXF                | New layers: swept outer/inner, wheel tracks, vehicle positions, encroachments   | Block insertion of vehicle outlines at intervals                    | Custom layer colours / linetypes                 |
| Output – Visual             | Matplotlib static plot (path + swept + carriageway)                              | Embedded matplotlib in Tkinter editor                               | Interactive zoom / pan plot (Plotly / PyQt)      |
| Output – Report             | Text + JSON: max steer angle, min radius, clearances, pass/fail                 | HTML report option                                                  | PDF export with tables & figures                 |
| Configuration               | Single project config.xml (vehicles, layers, speed, stop-lock rules)            | Command-line overrides                                              | YAML / TOML alternative                          |

### 3. Detailed Functional Specifications

#### 3.1 Vehicle XML Schema (normative)

```xml
<?xml version="1.0" encoding="utf-8"?>
<vehicle name="..." version="1.0">
  <metadata>
    <source>...</source>
    <units>metres</units>           <!-- only metres supported in v1 -->
    <last_edited>2026-02-16</last_edited>
  </metadata>

  <body>
    <width>2.60</width>
    <front_overhang>1.20</front_overhang>
    <rear_overhang>2.10</rear_overhang>
    <!-- if polygon omitted → rectangular body is assumed -->
    <polygon origin="steering_axle">
      <point x="..." y="..." />     <!-- x = forward, y = left, relative to steering axle centre -->
      ...
    </polygon>
  </body>

  <axles>
    <axle index="0">                <!-- index 0 = steering axle -->
      <longitudinal_pos>0.0</longitudinal_pos>
      <is_steering>true</is_steering>
      <track_width>2.05</track_width>
      <tyre_width>0.35</tyre_width>
      <max_steer_angle_deg>45.0</max_steer_angle_deg>
    </axle>
    <axle>
      <longitudinal_pos>-4.20</longitudinal_pos>
      <is_steering>false</is_steering>
      <track_width>2.05</track_width>
    </axle>
    ...
  </axles>
</vehicle>
```

#### 3.2 Project Configuration XML (config.xml)

```xml
<pySweptPathConfig version="1.1">
  <vehicles>
    <design_vehicle>vehicles/semi_wb50.xml</design_vehicle>
    <check_vehicle>vehicles/fire_appliance.xml</check_vehicle>     <!-- optional -->
  </vehicles>

  <dxf>
    <input_file>site_layout.dxf</input_file>
    <steering_layer>Steering_Centreline</steering_layer>
    <carriageway_layer>Carriageway_Boundary</carriageway_layer>
  </dxf>

  <simulation>
    <step_size_m>0.20</step_size_m>           <!-- along steering path -->
    <densify_arcs_to>0.10</densify_arcs_to>
  </simulation>

  <turning>
    <design_speed_kmh>5.0</design_speed_kmh>
    <stop_lock>
      <mode>full_lock</mode>                  <!-- full_lock | limited -->
      <max_steer_angle_deg>42.0</max_steer_angle_deg>   <!-- overrides vehicle value if set -->
      <min_turning_radius_m>11.8</min_turning_radius_m> <!-- informational / check -->
    </stop_lock>
  </turning>

  <output>
    <dxf>true</dxf>
    <dxf_prefix>Swept_</dxf_prefix>
    <plot>true</plot>
    <report>text,json</report>
  </output>
</pySweptPathConfig>
```

#### 3.3 Vehicle Editor GUI Requirements (Tkinter-based)

- **Main window modes**: New vehicle | Open XML | Edit current  
- **Canvas**: plan view, scale 1:50 default, zoom/pan, grid snap option  
- **Tools**:
  - Place steering axle (always at 0,0)
  - Add fixed axle (click or numeric input)
  - Draw body polygon (click points, close loop)
  - Rectangle body quick-draw (width + overhangs)
  - Set track widths, tyre widths, max steer angle
- **Preview pane**: shows Ackermann steering at 10°, 20°, 30°, full-lock
- **Validation**: highlight invalid configurations (negative wheelbase, overlapping axles, etc.)
- **Save / Export**: XML + optional PNG plan + PNG Ackermann preview

### 4. Technical Stack (Phase 1)

| Component          | Technology                            | Rationale                                      |
|--------------------|---------------------------------------|------------------------------------------------|
| Language           | Python 3.10 – 3.12                    | Wide availability, good typing                 |
| DXF I/O            | ezdxf                                 | Mature, handles hatches & bulges well          |
| Geometry           | shapely >= 2.0                        | Fast union, difference, buffering              |
| Numerics           | numpy                                 | Vector math, interpolation                     |
| Plotting           | matplotlib                            | Good enough static plots, Tkinter embeddable   |
| GUI (editor only)  | tkinter (built-in)                    | Zero extra install, acceptable for MVP         |
| XML parsing        | xml.etree.ElementTree (stdlib)        | No extra dependency                            |
| CLI                | argparse (stdlib)                     | Simple & sufficient                            |

**No internet access required at runtime.**

### 5. Acceptance Criteria (MVP)

1. Can load any simple closed HATCH + polyline from DXF  
2. Can simulate WB-50 design vehicle without crash  
3. Produces swept area within ~50 mm of AutoTURN on 15–30 m radius turns  
4. Correctly identifies encroachment when path is too tight  
5. Vehicle editor can create new vehicle → save XML → reload & simulate  
6. config.xml with check vehicle produces two swept areas & combined report  
7. Stops and clearly warns when steering angle exceeds stop-lock limit  
8. Runs end-to-end (dxf → simulation → dxf + plot + report) in < 8 seconds on typical 200 m path  

### 6. Roadmap – High-Level

Phase 1 (MVP – Q1/Q2 2026)  
- XML vehicle format + loader  
- Project config XML  
- Core incremental Ackermann simulator  
- DXF I/O & swept union  
- Basic clearance report  
- Tkinter vehicle editor  
- 10+ standard design vehicle XML files  

Phase 2 (2026–2027)  
- Reverse manoeuvres  
- Articulated vehicle support  
- Speed-based turning (larger radius at higher speed)  
- Streamlit / DearPyGui interactive simulator  
- QGIS plugin wrapper  

This document now contains **all requirements** collected through our conversation in a single, self-contained PRD.

If you would like to proceed to actual code implementation, please indicate priority:

1. Vehicle XML loader + dataclass  
2. Core simulation engine (incremental + Ackermann)  
3. Tkinter vehicle editor stub  
4. DXF input parser  
5. Full CLI skeleton with config.xml support  
6. Something else  

Ready when you are.