"""Finite 2 mm C ropes through the moving M6 guide mouths and cylindrical throats."""

from pathlib import Path
import argparse
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial.transform import Rotation
from common import CAD, OUT, load_motion, read, save
from u_springs import CAD_TO_ROD


def radial_extent(c, slope):
    """Farthest point of an oblique 1 mm radius cylinder cut by a plane at offset c."""
    norm = np.linalg.norm(slope)
    if norm < 1e-12:
        return np.linalg.norm(c) + 1.0
    u = slope / norm
    v = np.array([-u[1], u[0]])
    a = np.sqrt(1 + norm**2)

    def radius(t):
        return np.hypot(*(c + a * np.cos(t) * u + np.sin(t) * v))

    grid = np.linspace(0, 2 * np.pi, 33)
    vals = [radius(t) for t in grid[:-1]]
    i = np.argmax(vals)
    h = grid[1]
    return -minimize_scalar(
        lambda t: -radius(t), bounds=(grid[i] - h, grid[i] + h), method="bounded"
    ).fun


def bore_gap(points, throat, mouth, half_throat, half_plate):
    best = np.inf
    for u, v in zip(points, points[1:]):
        if v[2] <= u[2]:
            raise ValueError("Reversed station-frame rope segment")
        start = max(u[2], -half_plate)
        end = min(v[2], half_plate)
        if end < start:
            continue
        slope = (v[:2] - u[:2]) / (v[2] - u[2])
        for h in sorted(
            {start, end, *[k for k in (-half_throat, half_throat) if start < k < end]}
        ):
            c = u[:2] + (h - u[2]) * slope
            bore = throat + (mouth - throat) * np.clip(
                (abs(h) - half_throat) / (half_plate - half_throat), 0, 1
            )
            best = min(best, bore - radial_extent(c, slope))
    return best


def run(out):
    rod, z, T = load_motion()
    design = read(CAD / "guides_v3/design.json")
    radii = (
        design["rope_bore_mm"] / 2,
        design["rope_mouth_mm"] / 2,
        design["rope_throat_length_mm"] / 2,
        design["plate_thickness_mm"] / 2,
    )
    records = []
    support = read(out / "m6_support.json")["cases"]
    for step in (1709, 1710, 1885):
        d = rod.kinematic_metrics(z[step])[1]
        stations = (-24, -12, 12, 24)
        nodes = [40 + (st + 48) // 12 for st in stations]
        frames = d["frames"][nodes] @ CAD_TO_ROD
        origin = d["points"][nodes] * 1000
        for G in (500, 1500):
            measured = [
                next(
                    x
                    for x in support
                    if (x["step"], x["G_MPa"], x["gap_mm"], x["station_mm"])
                    == (step, G, 0.25, st)
                )
                for st in stations[1:-1]
            ]
            inc = np.array(
                [[0] * 6, *(x["guide_increment_mm_rad"] for x in measured), [0] * 6]
            )
            changed = frames @ Rotation.from_rotvec(inc[:, 3:]).as_matrix()
            centres = origin + np.einsum("nij,nj->ni", frames, inc[:, :3])
            for k, ray in enumerate(("up", "right", "down", "left")):
                offset = 1000 * CAD_TO_ROD.T @ rod.offsets3[2, k]
                ideal = origin + frames @ offset
                moved = centres + changed @ offset
                old = np.diff(ideal, axis=0)
                new = np.diff(moved, axis=0)
                delta_L = (
                    np.linalg.norm(new, axis=1).sum()
                    - np.linalg.norm(old, axis=1).sum()
                )
                u = old / np.linalg.norm(old, axis=1)[:, None]
                v = new / np.linalg.norm(new, axis=1)[:, None]
                for n, st in ((1, -12), (2, 12)):
                    vals = {}
                    for name, verts, R, c in (
                        ("ideal", ideal, frames, ideal),
                        ("original_rope_moved_bore", ideal, changed, moved),
                        ("recentered_rope_moved_bore", moved, changed, moved),
                    ):
                        points = (verts[n - 1 : n + 2] - c[n]) @ R[n]
                        vals[name + "_gap_mm"] = bore_gap(points, *radii)
                    records.append(
                        dict(
                            step=step,
                            G_MPa=G,
                            station_mm=st,
                            rope="C_" + ray,
                            bore_centre_shift_mm=np.linalg.norm(moved[n] - ideal[n]),
                            three_span_length_change_mm=delta_L,
                            force_vector_change_constant_T_N=np.linalg.norm(
                                T[step, 8 + k] * ((v[n] - v[n - 1]) - (u[n] - u[n - 1]))
                            ),
                            **vals,
                        )
                    )
    save(out / "m6_bores.json", records)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
