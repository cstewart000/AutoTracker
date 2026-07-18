"""Encroachment polygon, area, max penetration. See PDR §2."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False


@dataclass
class ClearanceResult:
    encroachment_area_m2: float
    max_penetration_m: float
    has_encroachment: bool
    min_lateral_clearance_m: float | None  # when no encroachment


def compute_clearance(swept_polygon, carriageway_polygon) -> ClearanceResult:
    """
    swept_polygon: Shapely polygon (or MultiPolygon) of swept area.
    carriageway_polygon: Shapely polygon of carriageway boundary.
    Returns encroachment area (m²), max penetration (m), pass/fail.
    """
    if not SHAPELY_OK or swept_polygon is None or carriageway_polygon is None:
        return ClearanceResult(0.0, 0.0, False, None)
    try:
        diff = swept_polygon.difference(carriageway_polygon)
        area = float(diff.area)
        if area < 1e-9:
            return ClearanceResult(0.0, 0.0, False, None)
        # Approximate max penetration by buffer negative then measure
        try:
            boundary = carriageway_polygon.boundary
            if boundary is None:
                max_pen = 0.0
            else:
                max_pen = diff.distance(boundary)
                max_pen = float(max_pen) if max_pen is not None else 0.0
        except Exception:
            max_pen = 0.0
        return ClearanceResult(
            encroachment_area_m2=area,
            max_penetration_m=max_pen,
            has_encroachment=True,
            min_lateral_clearance_m=None,
        )
    except Exception as e:
        logger.exception("Clearance computation failed: %s", e)
        return ClearanceResult(0.0, 0.0, False, None)
