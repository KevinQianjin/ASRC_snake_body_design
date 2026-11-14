"""Quantify idealized intermediate guide spacing for M5/M6 rope lanes.

Reads saved 8-cell/module simulation states and treats a guide as an ideal eyelet
at a material-frame node. It measures each straight rope span between guide
stations against the module's local lane. The resulting corridor margin is a
conservative screening estimate, not a deformed-solid contact simulation.
Run from this folder:
    python rope_guide_study.py ../lanes_20261113/results_lanes/minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import lanes

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAD = REPO / "cad" / "lanes_u4m2"
MODULE_NAMES = ("U1", "U2", "U3", "U4", "M5", "M6")
RAY_NAMES = ("up", "right", "down", "left")
DEFAULT_SPACINGS_MM = (96.0, 48.0, 24.0, 12.0)
SAFETY_CLEARANCE_MM = 1.0


def _corridor_clearances():
    design = json.loads((CAD / "lane_design.json").read_text(encoding="utf-8"))
    raw = design["M_lane_clearance_mm"]
    return {
        "B": min(raw[f"B@{ray}"] for ray in RAY_NAMES),
        "C": min(raw[f"C@{ray}"] for ray in RAY_NAMES),
    }


def _segment_deviation(p, F, i0, i1, off):
    """Return the maximum transverse guide-span deviation in local lane coordinates."""
    a = p[i0] + F[i0] @ off
    b = p[i1] + F[i1] @ off
    chord = b - a
    max_rad_out = max_rad_in = max_tang = max_norm = 0.0
    rad = off / np.linalg.norm(off)
    # This tangent convention matches rope_chord_check.py and the model's ray ordering.
    tan = np.cross(np.array([1.0, 0.0, 0.0]), rad)
    for i in range(i0 + 1, i1):
        n = F[i][:, 0]
        denom = float(np.dot(chord, n))
        if abs(denom) < 1e-12:
            continue
        t = float(np.dot(p[i] - a, n) / denom)
        if not 0.0 < t < 1.0:
            continue
        q = a + t * chord
        loc = F[i].T @ (q - p[i]) - off
        radial = float(np.dot(loc, rad))
        tangential = float(np.dot(loc, tan))
        transverse = float(np.linalg.norm(loc - np.dot(loc, n) * n))
        max_rad_out = max(max_rad_out, radial)
        max_rad_in = max(max_rad_in, -radial)
        max_tang = max(max_tang, abs(tangential))
        max_norm = max(max_norm, transverse)
    return max_rad_out, max_rad_in, max_tang, max_norm


def scan_state_archive(path, rod, guide_cells):
    data = np.load(path)
    measurements = {
        name: {set_name: dict(rad_out=0.0, rad_in=0.0, tang=0.0, deviation=0.0, samples=0)
               for set_name in ("B", "C")}
        for name in ("M5", "M6")
    }
    for key in data.files:
        if not key.endswith("_z8"):
            continue
        z = data[key]
        tension_key = key.replace("_z8", "_T8")
        _, _, details = rod.evaluate(z, data[tension_key], detail=True)
        p, F = details["points"], details["frames"]
        for j in (4, 5):
            module_name = MODULE_NAMES[j]
            first, last = j * rod.sub, (j + 1) * rod.sub
            set_indices = (1, 2) if j == 4 else (2,)
            step = guide_cells
            for set_index in set_indices:
                set_name = ("A", "B", "C")[set_index]
                record = measurements[module_name][set_name]
                for ray in range(4):
                    if rod.routes[set_index, j] == 0.0:
                        continue
                    off = rod.offsets3[set_index, ray]
                    for i0 in range(first, last, step):
                        i1 = i0 + step
                        r_out, r_in, tang, norm = _segment_deviation(p, F, i0, i1, off)
                        record["rad_out"] = max(record["rad_out"], r_out * 1000.0)
                        record["rad_in"] = max(record["rad_in"], r_in * 1000.0)
                        record["tang"] = max(record["tang"], tang * 1000.0)
                        record["deviation"] = max(record["deviation"], norm * 1000.0)
                        record["samples"] += 1
    return measurements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", nargs="+", type=Path, help="saved 8-cell/module NPZ state archives")
    parser.add_argument("--spacings", nargs="+", type=float, default=list(DEFAULT_SPACINGS_MM),
                        help="candidate guide pitches in mm (must align with 8 cells/module)")
    parser.add_argument("--output", type=Path, default=HERE / "rope_guide_study.json")
    args = parser.parse_args()

    lanes.install()
    import backbone

    rod = backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8, "niti18_E40")
    clearances = _corridor_clearances()
    report = {
        "method": "ideal material-frame eyelets; straight rope spans between guide stations",
        "scope": "path deviation and conservative corridor screen, not deformed-solid contact or friction",
        "source_archives": [str(p) for p in args.states],
        "safety_clearance_mm": SAFETY_CLEARANCE_MM,
        "modules": {},
    }
    for spacing in args.spacings:
        cells = int(round((spacing / 1000.0) / rod.l))
        if cells < 1 or cells > rod.sub or rod.sub % cells != 0 or abs(cells * rod.l - spacing / 1000.0) > 1e-8:
            raise ValueError(f"{spacing:g} mm does not align with 8-cell module resolution ({rod.l*1000:g} mm/cell)")
        aggregate = {name: {set_name: dict(rad_out=0.0, rad_in=0.0, tang=0.0, deviation=0.0, samples=0)
                            for set_name in ("B", "C")} for name in ("M5", "M6")}
        for archive in args.states:
            scanned = scan_state_archive(archive, rod, cells)
            for module_name in aggregate:
                for set_name, values in scanned[module_name].items():
                    out = aggregate[module_name][set_name]
                    for field in ("rad_out", "rad_in", "tang", "deviation"):
                        out[field] = max(out[field], values[field])
                    out["samples"] += values["samples"]
        for module_name in aggregate:
            for set_name, values in aggregate[module_name].items():
                if module_name == "M6" and set_name == "B":
                    continue
                values["static_corridor_clearance_mm"] = clearances[set_name]
                values["estimated_residual_clearance_mm"] = round(clearances[set_name] - values["deviation"], 3)
                values["passes_1mm_screen"] = values["estimated_residual_clearance_mm"] >= SAFETY_CLEARANCE_MM
                for key in ("rad_out", "rad_in", "tang", "deviation"):
                    values[key] = round(values[key], 3)
        report["modules"][f"guide_{spacing:g}mm"] = {
            "guide_spacing_mm": spacing,
            "guide_cells_per_span": cells,
            "intermediate_guides_per_module": int(96 // spacing) - 1,
            "results": aggregate,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["modules"], indent=2))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
