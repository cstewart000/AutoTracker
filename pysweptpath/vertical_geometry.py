"""Vertical profile bodies: tractor chord + hitch pin; trailer rigid about central axle only."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .vertical_sim import VerticalFrame, ground_tangent_secant, ground_tangent_unit, interp_z

if TYPE_CHECKING:
    from .vehicle import Vehicle, VerticalProfile


def _perp_up_stable(T: tuple[float, float]) -> tuple[float, float]:
    """Unit normal to T, stable (no flip); prefers +z component for road profiles."""
    a = math.atan2(T[1], T[0])
    return (-math.sin(a), math.cos(a))


def _point_on_deck_line(P0: tuple[float, float], T: tuple[float, float], s_target: float) -> tuple[float, float]:
    ux, uz = T
    if abs(ux) < 1e-9:
        t = 0.0 if abs(uz) < 1e-9 else (s_target - P0[0]) / uz
    else:
        t = (s_target - P0[0]) / ux
    return (P0[0] + t * ux, P0[1] + t * uz)


def trailer_central_pivot_xy(vehicle: "Vehicle", fr: VerticalFrame) -> tuple[float, float] | None:
    """Central trailer axle (chainage, wheel-centre z) for hinge marker; None if not multi-axle trailer."""
    idxs = [i for i, a in enumerate(vehicle.axles) if vehicle.get_segment_for_axle(a) == vehicle.num_segments() - 1]
    if len(idxs) < 3:
        return None
    idxs.sort(key=lambda i: vehicle.axles[i].longitudinal_pos)
    i_c = idxs[len(idxs) // 2]
    return (fr.axle_s[i_c], fr.z_wheel_center[i_c])


def articulation_wheel_xy(vehicle: "Vehicle", fr: VerticalFrame, path: np.ndarray, R: float) -> tuple[float, float] | None:
    """Articulation chainage at wheel-centre height on ground (hitch reference)."""
    arts = vehicle._art_list()
    if not arts:
        return None
    s_art = fr.s_ref + arts[0]
    return (s_art, interp_z(s_art, path) + R)


def segment_profile_polygons(
    vehicle: "Vehicle",
    fr: VerticalFrame,
    vp: "VerticalProfile",
    path: np.ndarray,
) -> list[list[tuple[float, float]]]:
    """
    Tractor (2 axles): bottom through hitch P_low along chord T; other logic unchanged.
    Trailer (3+ axles): rigid bar **only** about central axle C = (s_c, z_wheel_c). Pitch T from secant at s_c
    (smooth). Body ends at ±L along T from C (+ sill along N). Front/rear trailer axles do not define T.
    """
    R = vp.wheel_radius_m
    sill = vp.body_depth_m
    hw = float(vp.trailer_tangent_window_m)
    out: list[list[tuple[float, float]]] = []
    arts = vehicle._art_list()
    s_art: float | None = None
    P_low: tuple[float, float] | None = None
    if arts:
        s_art = fr.s_ref + arts[0]
        P_low = (s_art, interp_z(s_art, path) + R)

    for seg_idx in range(vehicle.num_segments()):
        idxs = [i for i, a in enumerate(vehicle.axles) if vehicle.get_segment_for_axle(a) == seg_idx]
        if not idxs:
            continue
        idxs.sort(key=lambda i: vehicle.axles[i].longitudinal_pos)
        body = vehicle.get_body_for_segment(seg_idx)
        fl = body.front_longitudinal_pos
        rl = body.rear_longitudinal_pos
        if fl is None or rl is None:
            fl = body.front_overhang
            rl = -body.rear_overhang
        s_rb = fr.s_ref + float(rl)
        s_fb = fr.s_ref + float(fl)

        if len(idxs) >= 3:
            i_c = idxs[len(idxs) // 2]
            pos_c = vehicle.axles[i_c].longitudinal_pos
            s_c = fr.axle_s[i_c]
            C = (s_c, fr.z_wheel_center[i_c])
            T = ground_tangent_secant(s_c, path, hw)
            N = _perp_up_stable(T)
            L_rear = abs(pos_c - rl)
            L_fwd = abs(fl - pos_c)
            br = (C[0] - L_rear * T[0] + sill * N[0], C[1] - L_rear * T[1] + sill * N[1])
            bf = (C[0] + L_fwd * T[0] + sill * N[0], C[1] + L_fwd * T[1] + sill * N[1])
        elif len(idxs) == 2:
            i0, i1 = idxs[0], idxs[-1]
            sr, sf = fr.axle_s[i0], fr.axle_s[i1]
            zwr, zwf = fr.z_wheel_center[i0], fr.z_wheel_center[i1]
            ds, dz = sf - sr, zwf - zwr
            L = math.hypot(ds, dz)
            T = (ds / L, dz / L) if L > 1e-9 else (1.0, 0.0)
            N = _perp_up_stable(T)
            touches_art = (
                P_low is not None
                and s_art is not None
                and (abs(s_rb - s_art) < 0.05 or abs(s_fb - s_art) < 0.05)
            )
            if touches_art:
                br = _point_on_deck_line(P_low, T, s_rb)
                bf = _point_on_deck_line(P_low, T, s_fb)
            else:
                s0 = fr.axle_s[idxs[0]]
                wc0 = (s0, interp_z(s0, path) + R)
                deck_c = (wc0[0] + sill * N[0], wc0[1] + sill * N[1])
                br = _point_on_deck_line(deck_c, T, s_rb)
                bf = _point_on_deck_line(deck_c, T, s_fb)
        else:
            ia = idxs[0]
            T = ground_tangent_unit(fr.axle_s[ia], path)
            N = _perp_up_stable(T)
            s0 = fr.axle_s[ia]
            wc0 = (s0, interp_z(s0, path) + R)
            deck_c = (wc0[0] + sill * N[0], wc0[1] + sill * N[1])
            br = _point_on_deck_line(deck_c, T, s_rb)
            bf = _point_on_deck_line(deck_c, T, s_fb)

        h = max(body.width * 0.45, 1.8)
        tr = (br[0] + h * N[0], br[1] + h * N[1])
        tf = (bf[0] + h * N[0], bf[1] + h * N[1])
        out.append([br, bf, tf, tr, br])
    return out
