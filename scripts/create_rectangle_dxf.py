"""Create test DXF: 20×60 m rectangle carriageway + centreline steering path."""

import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ezdxf required: pip install ezdxf", file=sys.stderr)
    sys.exit(1)

# 20 m wide, 60 m long — corners (0,0), (60,0), (60,20), (0,20)
WIDTH, LENGTH = 20.0, 60.0
carriageway_pts = [(0, 0), (LENGTH, 0), (LENGTH, WIDTH), (0, WIDTH)]

# Steering path: rectangular path (5,5) -> (5,15) -> (55,15) -> (55,5)
steering_pts = [(5.0, 5.0), (5.0, 15.0), (55.0, 15.0), (55.0, 5.0)]

doc = ezdxf.new("R2000")
msp = doc.modelspace()

doc.layers.add("Steering_Centreline", color=1)
msp.add_lwpolyline(steering_pts, dxfattribs={"layer": "Steering_Centreline"})

doc.layers.add("Carriageway_Boundary", color=2)
hatch = msp.add_hatch(color=2, dxfattribs={"layer": "Carriageway_Boundary"})
hatch.paths.add_polyline_path(carriageway_pts, is_closed=True)

out = Path(__file__).resolve().parent.parent / "input models" / "rectangle_20x60.dxf"
out.parent.mkdir(parents=True, exist_ok=True)
doc.saveas(str(out))
print(f"Created {out} (20×60 m rectangle, centreline path)")
