"""DXF read/write: steering path (polyline) and carriageway (hatch). See PDR §2."""

import logging
import math
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

try:
    import ezdxf
    from ezdxf.document import Drawing
except ImportError:
    ezdxf = None
    Drawing = None


def read_steering_path(doc: "Drawing", layer: str) -> list[tuple[float, float]]:
    """Extract polyline points from layer. Returns list of (x,y)."""
    if ezdxf is None:
        logger.error("ezdxf not installed")
        return []
    msp = doc.modelspace()
    points = []
    for e in msp.query(f'LINE LWPOLYLINE POLYLINE[layer=="{layer}"]'):
        if e.dxftype() == "LWPOLYLINE":
            for p in e.get_points("xy"):
                points.append((float(p[0]), float(p[1])))
        elif e.dxftype() == "LINE":
            points.append((float(e.dxf.start.x), float(e.dxf.start.y)))
            points.append((float(e.dxf.end.x), float(e.dxf.end.y)))
    logger.info("Read %d points from steering layer %s", len(points), layer)
    return points


def read_carriageway_hatch(doc: "Drawing", layer: str):
    """Get carriageway boundary as Shapely geometry. Returns None if not available."""
    if ezdxf is None:
        return None
    try:
        from shapely.geometry import Polygon
        from ezdxf.entities import Hatch
    except ImportError:
        return None
    msp = doc.modelspace()
    for e in msp.query(f'HATCH[layer=="{layer}"]'):
        if hasattr(e, "paths") and e.paths:
            path = e.paths[0]
            if hasattr(path, "vertices"):
                pts = [(v[0], v[1]) for v in path.vertices]
                if len(pts) >= 3:
                    return Polygon(pts)
    logger.warning(
        "Carriageway layer '%s' is not a closed hatch (or has no HATCH entity); continuing without carriageway boundary.",
        layer,
    )
    return None


def load_dxf(path: str | Path) -> "Drawing | None":
    """Load DXF file."""
    if ezdxf is None:
        logger.error("ezdxf not installed")
        return None
    path = Path(path)
    if not path.exists():
        logger.error("DXF file not found: %s", path)
        return None
    doc = ezdxf.readfile(str(path))
    logger.info("Loaded DXF: %s", path)
    return doc


def _body_outline_world_at_step(vehicle, positions: list, segment_poses: list | None, step: int):
    """Return list of segment polygons in world coords at given step (each segment = list of (x,y))."""
    from .envelope import body_outline_vehicle, transform_outline
    x, y, h = positions[step][0], positions[step][1], positions[step][2]
    if not segment_poses or step >= len(segment_poses) or len(segment_poses[step]) <= 1:
        outline = body_outline_vehicle(vehicle, segment_origin_m=0.0)
        return [transform_outline(outline, x, y, h)]
    row = segment_poses[step]
    out = []
    for seg_idx in range(len(row)):
        xk, yk, hk = row[seg_idx]
        body_k = vehicle.get_body_for_segment(seg_idx)
        origin_m = vehicle.get_origin_for_segment(seg_idx)
        outline = body_outline_vehicle(vehicle, body_k, segment_origin_m=origin_m)
        out.append(transform_outline(outline, xk, yk, hk))
    return out


def _vehicle_outline_local(vehicle):
    """Vehicle outline in local coords (steering axle at 0,0, heading 0). Returns list of segment polylines (closed)."""
    from .envelope import body_outline_vehicle
    num_seg = vehicle.num_segments()
    out = []
    for seg_idx in range(num_seg):
        origin_m = vehicle.get_origin_for_segment(seg_idx)
        body = vehicle.get_body_for_segment(seg_idx)
        outline = body_outline_vehicle(vehicle, body, segment_origin_m=origin_m)
        local_pts = [(origin_m + px, py) for px, py in outline]
        out.append(local_pts)
    return out


def write_swept_layers(
    doc: "Drawing",
    prefix: str,
    outer_pts: list,
    inner_pts: list,
    positions: list,
    encroachment_pts: list | None = None,
    vehicle=None,
    segment_poses: Sequence[Sequence[tuple[float, float, float]]] | None = None,
) -> None:
    """Write swept outer/inner, encroachment, corner traces, and vehicle start/end blocks."""
    if ezdxf is None or doc is None:
        return
    msp = doc.modelspace()
    if outer_pts:
        layer = f"{prefix}outer"
        if layer not in [l.dxf.name for l in doc.layers]:
            doc.layers.add(layer)
        msp.add_lwpolyline(outer_pts, dxfattribs={"layer": layer})
    if inner_pts:
        layer = f"{prefix}inner"
        if layer not in [l.dxf.name for l in doc.layers]:
            doc.layers.add(layer)
        msp.add_lwpolyline(inner_pts, dxfattribs={"layer": layer})
    if encroachment_pts:
        layer = f"{prefix}encroachment"
        if layer not in [l.dxf.name for l in doc.layers]:
            doc.layers.add(layer)
        msp.add_lwpolyline(encroachment_pts, dxfattribs={"layer": layer})

    if vehicle and positions:
        num_corners = 4 * vehicle.num_segments() if segment_poses and segment_poses and len(segment_poses[0]) > 1 else 4
        corner_traces = [[] for _ in range(num_corners)]
        for i in range(len(positions)):
            segs = _body_outline_world_at_step(vehicle, positions, segment_poses, i)
            flat = [p for seg in segs for p in seg]
            for j, pt in enumerate(flat[:num_corners]):
                if j < num_corners:
                    corner_traces[j].append(pt)
        layer_traces = f"{prefix}corner_traces"
        if layer_traces not in [l.dxf.name for l in doc.layers]:
            doc.layers.add(layer_traces)
        for trace in corner_traces:
            if len(trace) > 1:
                msp.add_lwpolyline(trace, dxfattribs={"layer": layer_traces})

        block_name = f"{prefix.rstrip('_')}VEHICLE"
        if block_name not in doc.blocks:
            blk = doc.blocks.new(block_name)
            for seg_pts in _vehicle_outline_local(vehicle):
                if len(seg_pts) >= 2:
                    closed = list(seg_pts) + [seg_pts[0]]
                    blk.add_lwpolyline(closed)
        layer_vehicle = f"{prefix}vehicle_positions"
        if layer_vehicle not in [l.dxf.name for l in doc.layers]:
            doc.layers.add(layer_vehicle)
        x0, y0, h0 = positions[0][0], positions[0][1], positions[0][2]
        msp.add_blockref(block_name, (x0, y0), dxfattribs={"layer": layer_vehicle, "rotation": math.degrees(h0)})
        if len(positions) > 1:
            x1, y1, h1 = positions[-1][0], positions[-1][1], positions[-1][2]
            msp.add_blockref(block_name, (x1, y1), dxfattribs={"layer": layer_vehicle, "rotation": math.degrees(h1)})
    logger.info("Written swept layers with prefix %s", prefix)


def write_vertical_profile_dxf(
    doc: "Drawing",
    path_sz: list[tuple[float, float]],
    prefix: str,
) -> None:
    """Add profile polylines (chainage, elevation); left-to-right = increasing X."""
    if ezdxf is None or doc is None:
        return
    layer_g = f"{prefix}profile_ground"
    if layer_g not in [l.dxf.name for l in doc.layers]:
        doc.layers.add(layer_g, color=3)
    msp = doc.modelspace()
    if len(path_sz) >= 2:
        msp.add_lwpolyline(path_sz, dxfattribs={"layer": layer_g})
    logger.info("Written vertical profile layer %s", layer_g)


def write_vertical_swept_extent_dxf(
    doc: "Drawing",
    extent_ring: list[tuple[float, float]],
    prefix: str,
) -> None:
    """Closed polyline: union of body profile over travel (vertical swept extent)."""
    if ezdxf is None or doc is None or len(extent_ring) < 3:
        return
    layer = f"{prefix}profile_extent"
    if layer not in [l.dxf.name for l in doc.layers]:
        doc.layers.add(layer, color=1)
    msp = doc.modelspace()
    msp.add_lwpolyline(extent_ring, close=True, dxfattribs={"layer": layer})
    logger.info("Written vertical swept extent layer %s", layer)
