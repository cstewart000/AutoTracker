"""Swept envelope: body outline in vehicle coords, transform, union. See PDR §2."""

import math
from typing import Sequence

logger = __import__("logging").getLogger(__name__)

try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    _SHAPELY = True
except ImportError:
    _SHAPELY = False


def body_outline_vehicle(
    vehicle, body: "Body | None" = None, segment_origin_m: float | None = None
) -> list[tuple[float, float]]:
    """Body polygon in segment-local coords (x=forward, y=left). If body is None, uses vehicle.body.
    When segment_origin_m is set and body has front/rear_longitudinal_pos, extents use that frame (same as axles)."""
    b = body if body is not None else vehicle.body
    if b.polygon and len(b.polygon) >= 2:
        return list(b.polygon)
    w2 = b.width / 2
    fl = getattr(b, "front_longitudinal_pos", None)
    rl = getattr(b, "rear_longitudinal_pos", None)
    if fl is not None and rl is not None and segment_origin_m is not None:
        x_front = fl - segment_origin_m
        x_rear = rl - segment_origin_m
        return [(x_rear, -w2), (x_front, -w2), (x_front, w2), (x_rear, w2)]
    f, r = b.front_overhang, b.rear_overhang
    return [(-r, -w2), (f, -w2), (f, w2), (-r, w2)]


def transform_outline(
    points: Sequence[tuple[float, float]],
    cx: float, cy: float, heading_rad: float,
) -> list[tuple[float, float]]:
    """Transform body outline from vehicle to world coords."""
    c, s = math.cos(heading_rad), math.sin(heading_rad)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in points]


def swept_envelope_polygon(
    positions: Sequence[tuple[float, float, float]],
    vehicle,
    segment_poses: Sequence[Sequence[tuple[float, float, float]]] | None = None,
) -> "Polygon | None":
    """Union of vehicle body at each position. segment_poses[t][k] = pose for segment k at step t."""
    if not _SHAPELY or not positions:
        return None
    has_segment_poses = (
        segment_poses is not None
        and len(segment_poses) == len(positions)
        and len(segment_poses[0]) >= 1
    )
    polys = []
    for i, (x, y, h) in enumerate(positions):
        if has_segment_poses:
            row = segment_poses[i]
            for seg_idx in range(len(row)):
                xk, yk, hk = row[seg_idx]
                body_k = vehicle.get_body_for_segment(seg_idx)
                origin_m = vehicle.get_origin_for_segment(seg_idx)
                outline = body_outline_vehicle(vehicle, body_k, segment_origin_m=origin_m)
                pts = transform_outline(outline, xk, yk, hk)
                if len(pts) >= 3:
                    try:
                        polys.append(Polygon(pts))
                    except Exception as e:
                        logger.debug("Failed to create segment %d polygon: %s", seg_idx, e)
        else:
            outline = body_outline_vehicle(vehicle, segment_origin_m=0.0)
            pts = transform_outline(outline, x, y, h)
            if len(pts) >= 3:
                polys.append(Polygon(pts))
    if not polys:
        return None
    return unary_union(polys)
