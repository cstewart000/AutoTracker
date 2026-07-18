"""Create demo DXF: semi-circle steering path + carriageway boundary hatch."""

import math
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ezdxf required: pip install ezdxf", file=sys.stderr)
    sys.exit(1)

# Semi-circle: radius 20 m, from (20,0) via (0,20) to (-20,0) — left turn
R = 20.0
N = 80  # points along arc
points_steering = [
    (R * math.cos(t), R * math.sin(t))
    for t in [math.pi * i / (N - 1) for i in range(N)]
]

doc = ezdxf.new("R2000")
msp = doc.modelspace()

doc.layers.add("Steering_Centreline", color=1)
msp.add_lwpolyline(points_steering, dxfattribs={"layer": "Steering_Centreline"})

# Carriageway: rectangle enclosing semi-circle (with margin)
margin = 5.0
carriageway_pts = [
    (-R - margin, -margin),
    (R + margin, -margin),
    (R + margin, R + margin),
    (-R - margin, R + margin),
]
doc.layers.add("Carriageway_Boundary", color=2)
hatch = msp.add_hatch(color=2, dxfattribs={"layer": "Carriageway_Boundary"})
hatch.paths.add_polyline_path(carriageway_pts, is_closed=True)

out = Path(__file__).resolve().parent.parent / "demo.dxf"
doc.saveas(str(out))
print(f"Created {out} (semi-circle R={R}m, carriageway boundary)")
