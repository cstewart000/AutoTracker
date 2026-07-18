"""Vehicle XML loader and dataclass. See PDR §3.1."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def write_vehicle(vehicle: "Vehicle", path: str | Path) -> None:
    """Write vehicle to XML file (PDR §3.1 format)."""
    path = Path(path)
    root = ET.Element("vehicle", name=vehicle.name, version=vehicle.version)
    meta = ET.SubElement(root, "metadata")
    ET.SubElement(meta, "source").text = "pySweptPath"
    ET.SubElement(meta, "units").text = "metres"
    # Write body segments if articulated, otherwise single body
    arts = getattr(vehicle, "articulation_positions_m", None) or (
        [vehicle.articulation_longitudinal_m] if vehicle.articulation_longitudinal_m is not None else []
    )
    segs = getattr(vehicle, "body_segments", None)
    if arts and (segs or vehicle.front_body or vehicle.rear_body):
        segments_el = ET.SubElement(root, "body_segments")
        if segs:
            for idx, b in enumerate(segs):
                seg_el = ET.SubElement(segments_el, "segment", index=str(idx))
                ET.SubElement(seg_el, "width").text = str(b.width)
                if getattr(b, "front_longitudinal_pos", None) is not None and getattr(b, "rear_longitudinal_pos", None) is not None:
                    ET.SubElement(seg_el, "front_longitudinal").text = str(b.front_longitudinal_pos)
                    ET.SubElement(seg_el, "rear_longitudinal").text = str(b.rear_longitudinal_pos)
                else:
                    ET.SubElement(seg_el, "front_overhang").text = str(b.front_overhang)
                    ET.SubElement(seg_el, "rear_overhang").text = str(b.rear_overhang)
                if b.polygon:
                    poly = ET.SubElement(seg_el, "polygon", origin="segment")
                    for x, y in b.polygon:
                        ET.SubElement(poly, "point", x=str(x), y=str(y))
        else:
            if vehicle.front_body:
                front_el = ET.SubElement(segments_el, "front")
                ET.SubElement(front_el, "width").text = str(vehicle.front_body.width)
                b = vehicle.front_body
                if getattr(b, "front_longitudinal_pos", None) is not None and getattr(b, "rear_longitudinal_pos", None) is not None:
                    ET.SubElement(front_el, "front_longitudinal").text = str(b.front_longitudinal_pos)
                    ET.SubElement(front_el, "rear_longitudinal").text = str(b.rear_longitudinal_pos)
                else:
                    ET.SubElement(front_el, "front_overhang").text = str(b.front_overhang)
                    ET.SubElement(front_el, "rear_overhang").text = str(b.rear_overhang)
                if b.polygon:
                    poly = ET.SubElement(front_el, "polygon", origin="steering_axle")
                    for x, y in vehicle.front_body.polygon:
                        ET.SubElement(poly, "point", x=str(x), y=str(y))
            if vehicle.rear_body:
                rear_el = ET.SubElement(segments_el, "rear")
                b = vehicle.rear_body
                ET.SubElement(rear_el, "width").text = str(b.width)
                if getattr(b, "front_longitudinal_pos", None) is not None and getattr(b, "rear_longitudinal_pos", None) is not None:
                    ET.SubElement(rear_el, "front_longitudinal").text = str(b.front_longitudinal_pos)
                    ET.SubElement(rear_el, "rear_longitudinal").text = str(b.rear_longitudinal_pos)
                else:
                    ET.SubElement(rear_el, "front_overhang").text = str(b.front_overhang)
                    ET.SubElement(rear_el, "rear_overhang").text = str(b.rear_overhang)
                if b.polygon:
                    poly = ET.SubElement(rear_el, "polygon", origin="articulation")
                    for x, y in vehicle.rear_body.polygon:
                        ET.SubElement(poly, "point", x=str(x), y=str(y))
    else:
        # Single body (legacy or non-articulated)
        body_el = ET.SubElement(root, "body")
        ET.SubElement(body_el, "width").text = str(vehicle.body.width)
        ET.SubElement(body_el, "front_overhang").text = str(vehicle.body.front_overhang)
        ET.SubElement(body_el, "rear_overhang").text = str(vehicle.body.rear_overhang)
        if vehicle.body.polygon:
            poly = ET.SubElement(body_el, "polygon", origin="steering_axle")
            for x, y in vehicle.body.polygon:
                ET.SubElement(poly, "point", x=str(x), y=str(y))
    axles_el = ET.SubElement(root, "axles")
    for i, a in enumerate(vehicle.axles):
        ax = ET.SubElement(axles_el, "axle", index=str(i))
        ET.SubElement(ax, "longitudinal_pos").text = str(a.longitudinal_pos)
        ET.SubElement(ax, "is_steering").text = "true" if a.is_steering else "false"
        ET.SubElement(ax, "track_width").text = str(a.track_width)
        ET.SubElement(ax, "tyre_width").text = str(a.tyre_width)
        if a.max_steer_angle_deg is not None:
            ET.SubElement(ax, "max_steer_angle_deg").text = str(a.max_steer_angle_deg)
        if getattr(a, "steering_group_id", None) is not None:
            ET.SubElement(ax, "steering_group").text = str(a.steering_group_id)
    if getattr(vehicle, "steering_groups", None):
        sg_el = ET.SubElement(root, "steering_groups")
        for g in vehicle.steering_groups:
            gr = ET.SubElement(sg_el, "group", id=str(g.id), role=g.role)
            if g.ref is not None:
                gr.set("ref", str(g.ref))
            if g.inverse:
                gr.set("inverse", "true")
    if getattr(vehicle, "articulation_positions_m", None):
        arts_el = ET.SubElement(root, "articulations")
        for pos in vehicle.articulation_positions_m:
            ET.SubElement(arts_el, "longitudinal_pos").text = str(pos)
    elif getattr(vehicle, "articulation_longitudinal_m", None) is not None:
        art = ET.SubElement(root, "articulation")
        ET.SubElement(art, "longitudinal_pos").text = str(vehicle.articulation_longitudinal_m)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True, default_namespace=None)
    logger.info("Wrote vehicle to %s", path)


@dataclass
class SteeringGroup:
    """Steering group: primary (tracks path) or subordinate (follows a primary, optionally inverse)."""
    id: int  # group id, used in axle steering_group
    role: str  # "primary" | "subordinate"
    ref: int | None = None  # for subordinate: primary group id
    inverse: bool = False  # for subordinate: steer opposite to primary


@dataclass
class Axle:
    index: int
    longitudinal_pos: float  # m, 0 = steering axle
    is_steering: bool
    track_width: float  # m
    tyre_width: float = 0.35
    max_steer_angle_deg: float | None = None
    steering_group_id: int | None = None  # which steering group (default 0 = primary)


@dataclass
class VerticalProfile:
    """Longitudinal profile / vertical-plane simulation (chainage vs elevation)."""
    wheel_radius_m: float = 0.45  # tyre outer radius (m)
    ground_clearance_m: float = 0.25  # min required chord–terrain margin (m)
    body_depth_m: float = 0.35  # body sill below wheel-centre line for drawing (m)
    trailer_tangent_window_m: float = 4.0  # secant half-width at central axle — smooth pitch (no vertex snap)


@dataclass
class Body:
    width: float
    front_overhang: float = 0.0  # fallback when longitudinal not set
    rear_overhang: float = 0.0
    front_longitudinal_pos: float | None = None  # same frame as axles (0 = steering)
    rear_longitudinal_pos: float | None = None
    polygon: list[tuple[float, float]] | None = None  # (x,y) rel to segment origin


@dataclass
class Segment:
    """A vehicle segment: axles and a body. Body can extend beyond articulations and overlap other segments."""
    axles: list[Axle]  # axles in this segment (longitudinal_pos in global vehicle coords)
    body: Body  # body attached to this segment (extents in global longitudinal coords)


@dataclass
class Vehicle:
    name: str
    version: str
    body: Body  # Default/legacy body (used if no segments defined)
    axles: list[Axle] = field(default_factory=list)
    articulation_longitudinal_m: float | None = None  # first/legacy single pivot (backward compat)
    articulation_positions_m: list[float] = field(default_factory=list)  # all pivots front-to-rear (e.g. [-3.8, -10.8])
    front_body: Body | None = None  # Front segment (single articulation)
    rear_body: Body | None = None   # Rear segment (single articulation)
    body_segments: list[Body] | None = None  # N+1 segments for N articulations (multi-articulation)
    steering_groups: list[SteeringGroup] | None = None  # primary/subordinate steering groups
    segments: list[Segment] | None = None  # segment-based view: each segment has axles + body (optional)
    vertical: VerticalProfile | None = None  # optional profile-mode geometry

    @property
    def steering_axle(self) -> Axle | None:
        """First steering axle in a primary group (or first steering axle if no groups)."""
        groups = self.steering_groups or []
        primary_ids = {g.id for g in groups if g.role == "primary"}
        for a in self.axles:
            if not a.is_steering:
                continue
            gid = a.steering_group_id if a.steering_group_id is not None else 0
            if not groups or gid in primary_ids:
                return a
        for a in self.axles:
            if a.is_steering:
                return a
        return None

    def _steering_group_by_id(self, gid: int) -> SteeringGroup | None:
        for g in self.steering_groups or []:
            if g.id == gid:
                return g
        return None

    def get_steer_angle_for_axle(self, axle_index: int, primary_steer_deg: float) -> float:
        """Steer angle (deg) for this axle given primary group steer. Non-steering axles return 0."""
        if axle_index < 0 or axle_index >= len(self.axles):
            return 0.0
        axle = self.axles[axle_index]
        if not axle.is_steering:
            return 0.0
        gid = axle.steering_group_id if axle.steering_group_id is not None else 0
        group = self._steering_group_by_id(gid)
        if group is None:
            return primary_steer_deg  # default: same as primary
        if group.role == "primary":
            return primary_steer_deg
        if group.inverse:
            return -primary_steer_deg
        return primary_steer_deg

    def _art_list(self) -> list[float]:
        """Canonical list of articulation positions (front to rear)."""
        if self.articulation_positions_m:
            return self.articulation_positions_m
        if self.articulation_longitudinal_m is not None:
            return [self.articulation_longitudinal_m]
        return []

    def num_segments(self) -> int:
        """Number of body/pose segments (1 + number of articulations)."""
        if self.segments:
            return len(self.segments)
        n = len(self._art_list())
        return max(1, n + 1) if n else 1

    def get_segment_for_axle(self, axle: Axle) -> int:
        """Segment index (0=front) for this axle."""
        if self.segments:
            for i, seg in enumerate(self.segments):
                if axle in seg.axles:
                    return i
            return 0
        arts = self._art_list()
        if not arts:
            return 0
        pos = axle.longitudinal_pos
        for k, a in enumerate(arts):
            if pos >= a:
                return k
        return len(arts)

    def get_origin_for_segment(self, seg: int) -> float:
        """Longitudinal origin (m) for segment seg. Segment 0 = 0, segment k = arts[k-1]."""
        arts = self._art_list()
        if seg <= 0 or not arts:
            return 0.0
        if seg <= len(arts):
            return arts[seg - 1]
        return arts[-1]

    def get_body_for_segment(self, seg: int) -> Body:
        """Body for segment seg. Uses segments[seg].body when segments set, else body_segments/front_body/rear_body."""
        if self.segments and 0 <= seg < len(self.segments):
            return self.segments[seg].body
        if self.body_segments and 0 <= seg < len(self.body_segments):
            return self.body_segments[seg]
        arts = self._art_list()
        if len(arts) == 1:
            return self.front_body if seg == 0 and self.front_body else (self.rear_body if seg == 1 and self.rear_body else self.body)
        return self.body

    def get_body_for_axle(self, axle: Axle) -> Body:
        """Return the body segment that should be used for a given axle."""
        return self.get_body_for_segment(self.get_segment_for_axle(axle))


def _parse_float(elem: ET.Element | None, default: float = 0.0) -> float:
    if elem is None or elem.text is None:
        return default
    try:
        return float(elem.text.strip())
    except ValueError:
        return default


def _segment_index_for_pos(pos: float, arts: list[float]) -> int:
    """Segment index for an axle at longitudinal position pos."""
    if not arts:
        return 0
    for k, a in enumerate(arts):
        if pos >= a:
            return k
    return len(arts)


def _build_segments_from_legacy(vehicle: "Vehicle") -> list[Segment]:
    """Build segment list from flat axles + body_segments/front_body/rear_body + articulations."""
    arts = vehicle._art_list()
    num_seg = max(1, len(arts) + 1) if arts else 1
    out: list[Segment] = []
    for seg_idx in range(num_seg):
        seg_axles = [a for a in vehicle.axles if _segment_index_for_pos(a.longitudinal_pos, arts) == seg_idx]
        body = vehicle.get_body_for_segment(seg_idx)
        out.append(Segment(axles=seg_axles, body=body))
    return out


def load_vehicle(path: str | Path) -> Vehicle:
    path = Path(path)
    logger.info("Loading vehicle from %s", path)
    tree = ET.parse(path)
    root = tree.getroot()
    name = root.get("name", "unknown")
    version = root.get("version", "1.0")

    def _parse_body(elem: ET.Element | None) -> Body | None:
        """Parse body: prefers front_longitudinal/rear_longitudinal (same frame as axles)."""
        if elem is None:
            return None
        width = _parse_float(elem.find("width"), 2.6)
        front_oh = _parse_float(elem.find("front_overhang"), 1.2)
        rear_oh = _parse_float(elem.find("rear_overhang"), 2.1)
        fl, rl = elem.find("front_longitudinal"), elem.find("rear_longitudinal")
        front_long = None
        rear_long = None
        if fl is not None and fl.text:
            try:
                front_long = float(fl.text.strip())
            except ValueError:
                pass
        if rl is not None and rl.text:
            try:
                rear_long = float(rl.text.strip())
            except ValueError:
                pass
        poly_el = elem.find("polygon")
        polygon = None
        if poly_el is not None:
            polygon = []
            for pt in poly_el.findall("point"):
                x = _parse_float(pt.get("x"), 0.0)
                y = _parse_float(pt.get("y"), 0.0)
                polygon.append((x, y))
        return Body(
            width=width,
            front_overhang=front_oh,
            rear_overhang=rear_oh,
            front_longitudinal_pos=front_long,
            rear_longitudinal_pos=rear_long,
            polygon=polygon,
        )
    
    # Articulation positions: multiple <articulations> or single <articulation>
    articulation_positions_m: list[float] = []
    multi_arts_el = root.find("articulations")
    if multi_arts_el is not None:
        for el in multi_arts_el.findall("longitudinal_pos"):
            if el.text:
                try:
                    articulation_positions_m.append(float(el.text.strip()))
                except ValueError:
                    pass
    art_m = None
    art_el = root.find("articulation/longitudinal_pos")
    if art_el is not None and art_el.text:
        try:
            art_m = float(art_el.text.strip())
        except ValueError:
            pass
    if not articulation_positions_m and art_m is not None:
        articulation_positions_m = [art_m]

    # Check for body_segments (articulated) first
    segments_el = root.find("body_segments")
    front_body = None
    rear_body = None
    body_segments: list[Body] | None = None
    if segments_el is not None:
        front_body = _parse_body(segments_el.find("front"))
        rear_body = _parse_body(segments_el.find("rear"))
        # Multiple segments: <segment index="0">, <segment index="1">, ...
        seg_list = sorted(segments_el.findall("segment"), key=lambda e: int(e.get("index", 0)))
        if seg_list:
            body_segments = []
            for seg_el in seg_list:
                b = _parse_body(seg_el)
                if b:
                    body_segments.append(b)

    # Parse default body (legacy or fallback)
    body_el = root.find("body")
    if body_el is None and segments_el is None:
        raise ValueError("Vehicle XML must have <body> or <body_segments>")
    body = _parse_body(body_el) if body_el is not None else Body(width=2.6, front_overhang=1.2, rear_overhang=2.1, polygon=None)

    # Steering groups: <steering_groups><group id="0" role="primary"/><group id="1" role="subordinate" ref="0" inverse="true"/></steering_groups>
    steering_groups: list[SteeringGroup] | None = None
    sg_root = root.find("steering_groups")
    if sg_root is not None:
        steering_groups = []
        for g_el in sg_root.findall("group"):
            gid = int(g_el.get("id", 0))
            role = (g_el.get("role") or "primary").strip().lower()
            ref_attr = g_el.get("ref")
            ref = int(ref_attr) if ref_attr is not None else None
            inv = (g_el.get("inverse") or "").strip().lower() in ("true", "1", "yes")
            steering_groups.append(SteeringGroup(id=gid, role=role, ref=ref, inverse=inv))

    axles = []
    for i, ax_el in enumerate(root.findall("axles/axle")):
        pos = _parse_float(ax_el.find("longitudinal_pos"), 0.0)
        steer_el = ax_el.find("is_steering")
        is_steer = (steer_el.text or "").strip().lower() == "true" if steer_el is not None else (i == 0)
        track = _parse_float(ax_el.find("track_width"), 2.05)
        tyre = _parse_float(ax_el.find("tyre_width"), 0.35)
        max_steer = ax_el.find("max_steer_angle_deg")
        max_steer_deg = float(max_steer.text) if max_steer is not None and max_steer.text else None
        sg_el = ax_el.find("steering_group")
        steering_group_id = None
        if sg_el is not None and sg_el.text:
            try:
                steering_group_id = int(sg_el.text.strip())
            except ValueError:
                pass
        axles.append(
            Axle(
                index=i,
                longitudinal_pos=pos,
                is_steering=is_steer,
                track_width=track,
                tyre_width=tyre,
                max_steer_angle_deg=max_steer_deg,
                steering_group_id=steering_group_id,
            )
        )
    art_single = articulation_positions_m[0] if len(articulation_positions_m) == 1 else None
    vp_el = root.find("vertical_profile")
    vertical: VerticalProfile | None = None
    if vp_el is not None:
        vertical = VerticalProfile(
            wheel_radius_m=_parse_float(vp_el.find("wheel_radius_m"), 0.45),
            ground_clearance_m=_parse_float(vp_el.find("ground_clearance_m"), 0.25),
            body_depth_m=_parse_float(vp_el.find("body_depth_m"), 0.35),
            trailer_tangent_window_m=_parse_float(vp_el.find("trailer_tangent_window_m"), 4.0),
        )

    v = Vehicle(
        name=name,
        version=version,
        body=body,
        axles=axles,
        articulation_longitudinal_m=art_single,
        articulation_positions_m=articulation_positions_m,
        front_body=front_body,
        rear_body=rear_body,
        body_segments=body_segments,
        steering_groups=steering_groups,
        segments=None,
        vertical=vertical,
    )
    if v.body_segments or (v.front_body and v.rear_body):
        v.segments = _build_segments_from_legacy(v)
    return v
