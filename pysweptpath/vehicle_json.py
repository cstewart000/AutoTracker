"""Vehicle JSON (editor) ↔ Vehicle dataclass conversion."""

from __future__ import annotations

from typing import Any

from .vehicle import Axle, Body, Vehicle


def body_to_dict(b: Body) -> dict[str, Any]:
    d: dict[str, Any] = {
        "width": float(b.width),
        "front_overhang": float(b.front_overhang),
        "rear_overhang": float(b.rear_overhang),
    }
    if b.front_longitudinal_pos is not None:
        d["front_longitudinal"] = float(b.front_longitudinal_pos)
    if b.rear_longitudinal_pos is not None:
        d["rear_longitudinal"] = float(b.rear_longitudinal_pos)
    if b.polygon:
        d["polygon"] = [[float(x), float(y)] for x, y in b.polygon]
    return d


def body_from_dict(d: dict[str, Any] | None) -> Body:
    if not d:
        return Body(width=2.6, front_overhang=1.2, rear_overhang=2.1)
    poly = d.get("polygon")
    polygon = None
    if poly and len(poly) >= 2:
        polygon = [(float(p[0]), float(p[1])) for p in poly]
    fl = d.get("front_longitudinal")
    rl = d.get("rear_longitudinal")
    return Body(
        width=float(d.get("width", 2.6)),
        front_overhang=float(d.get("front_overhang", 1.2)),
        rear_overhang=float(d.get("rear_overhang", 2.1)),
        front_longitudinal_pos=float(fl) if fl is not None else None,
        rear_longitudinal_pos=float(rl) if rl is not None else None,
        polygon=polygon,
    )


def vehicle_to_dict(v: Vehicle) -> dict[str, Any]:
    """Serialize vehicle for the web editor."""
    axles = []
    for a in v.axles:
        ax: dict[str, Any] = {
            "index": a.index,
            "longitudinal_pos": float(a.longitudinal_pos),
            "is_steering": bool(a.is_steering),
            "track_width": float(a.track_width),
            "tyre_width": float(a.tyre_width),
        }
        if a.max_steer_angle_deg is not None:
            ax["max_steer_angle_deg"] = float(a.max_steer_angle_deg)
        if a.steering_group_id is not None:
            ax["steering_group"] = int(a.steering_group_id)
        axles.append(ax)

    arts = list(v.articulation_positions_m) if v.articulation_positions_m else []
    if not arts and v.articulation_longitudinal_m is not None:
        arts = [float(v.articulation_longitudinal_m)]

    out: dict[str, Any] = {
        "name": v.name,
        "version": v.version or "1.0",
        "body": body_to_dict(v.body),
        "axles": axles,
        "articulation_positions_m": [float(a) for a in arts],
    }
    if v.front_body is not None:
        out["front_body"] = body_to_dict(v.front_body)
    if v.rear_body is not None:
        out["rear_body"] = body_to_dict(v.rear_body)
    if v.body_segments:
        out["body_segments"] = [body_to_dict(b) for b in v.body_segments]

    # Editor convenience: overall dimensions
    xs = [a.longitudinal_pos for a in v.axles]
    if v.body.front_longitudinal_pos is not None:
        xs.append(v.body.front_longitudinal_pos)
    if v.body.rear_longitudinal_pos is not None:
        xs.append(v.body.rear_longitudinal_pos)
    if not xs:
        xs = [0.0]
    out["meta"] = {
        "x_min": min(xs) - float(v.body.rear_overhang or 0),
        "x_max": max(xs) + float(v.body.front_overhang or 0),
        "width": float(v.body.width),
        "num_axles": len(v.axles),
        "articulated": bool(arts),
    }
    return out


def vehicle_from_dict(data: dict[str, Any]) -> Vehicle:
    """Build Vehicle from editor JSON. Validates basics."""
    if not isinstance(data, dict):
        raise ValueError("Vehicle payload must be an object")
    name = str(data.get("name") or "Custom vehicle")
    version = str(data.get("version") or "1.0")
    body = body_from_dict(data.get("body") if isinstance(data.get("body"), dict) else data)

    # Allow flat width/overhangs at top level (simple editor form)
    if "body" not in data and ("width" in data or "front_overhang" in data):
        body = Body(
            width=float(data.get("width", body.width)),
            front_overhang=float(data.get("front_overhang", body.front_overhang)),
            rear_overhang=float(data.get("rear_overhang", body.rear_overhang)),
            front_longitudinal_pos=body.front_longitudinal_pos,
            rear_longitudinal_pos=body.rear_longitudinal_pos,
            polygon=body.polygon,
        )

    raw_axles = data.get("axles") or []
    if not raw_axles:
        raise ValueError("Vehicle needs at least one axle")
    axles: list[Axle] = []
    for i, a in enumerate(raw_axles):
        axles.append(
            Axle(
                index=int(a.get("index", i)),
                longitudinal_pos=float(a.get("longitudinal_pos", 0.0)),
                is_steering=bool(a.get("is_steering", i == 0)),
                track_width=float(a.get("track_width", 2.05)),
                tyre_width=float(a.get("tyre_width", 0.35)),
                max_steer_angle_deg=(
                    float(a["max_steer_angle_deg"])
                    if a.get("max_steer_angle_deg") is not None
                    else None
                ),
                steering_group_id=(
                    int(a["steering_group"])
                    if a.get("steering_group") is not None
                    else None
                ),
            )
        )
    # Ensure at least one steering axle
    if not any(a.is_steering for a in axles):
        axles[0].is_steering = True

    arts = [float(x) for x in (data.get("articulation_positions_m") or [])]
    if not arts and data.get("articulation_longitudinal_m") is not None:
        arts = [float(data["articulation_longitudinal_m"])]
    art_single = arts[0] if len(arts) == 1 else None

    front_body = body_from_dict(data.get("front_body")) if data.get("front_body") else None
    rear_body = body_from_dict(data.get("rear_body")) if data.get("rear_body") else None
    segs_raw = data.get("body_segments")
    body_segments = None
    if segs_raw:
        body_segments = [body_from_dict(s) for s in segs_raw]

    v = Vehicle(
        name=name,
        version=version,
        body=body,
        axles=axles,
        articulation_longitudinal_m=art_single,
        articulation_positions_m=arts,
        front_body=front_body,
        rear_body=rear_body,
        body_segments=body_segments,
    )
    if v.body_segments or (v.front_body and v.rear_body):
        from .vehicle import _build_segments_from_legacy

        v.segments = _build_segments_from_legacy(v)
    return v


def editor_outline(v: Vehicle) -> dict[str, Any]:
    """Plan-view geometry for canvas (vehicle frame: x forward, y left)."""
    from .envelope import body_outline_vehicle

    bodies = []
    n = v.num_segments()
    for seg in range(n):
        body = v.get_body_for_segment(seg)
        origin = v.get_origin_for_segment(seg)
        outline = body_outline_vehicle(v, body, segment_origin_m=origin)
        # Convert segment-local to global vehicle frame
        global_pts = [(x + origin, y) for x, y in outline]
        bodies.append({"segment": seg, "outline": global_pts, "origin_m": origin})

    axles = [
        {
            "index": a.index,
            "x": a.longitudinal_pos,
            "track_width": a.track_width,
            "is_steering": a.is_steering,
            "tyre_width": a.tyre_width,
        }
        for a in v.axles
    ]
    arts = list(v.articulation_positions_m) if v.articulation_positions_m else []
    if not arts and v.articulation_longitudinal_m is not None:
        arts = [v.articulation_longitudinal_m]
    return {
        "name": v.name,
        "bodies": bodies,
        "axles": axles,
        "articulations": arts,
    }
