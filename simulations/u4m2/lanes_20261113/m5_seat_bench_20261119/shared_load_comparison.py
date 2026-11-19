"""Compare the same retained M5 seat using two whole-arm boundary conditions at hold 146."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def compare(results, previous, updated):
    case = "146"
    group = results / "shared_load_case"

    def read(path):
        return json.loads(path.read_text())

    baseline = read(results / "coupled_fine" / f"{case}.json")
    current = read(group / f"{case}.json")
    if baseline["status"] != "converged" or current["status"] != "converged":
        raise ValueError(
            "A converged structural solution is required for each boundary condition"
        )
    prev_cad = read(results / "coupled_cad_refined_targets.json")
    curr_cad = read(group / "cad_146.json")
    for key in ("local_surface_edge_mm", "other_body_surface_edge_mm", "solid_level"):
        if prev_cad[key] != curr_cad[key]:
            raise ValueError("The clearance comparison requires matching meshes")

    def sites(source):
        return {
            (a["station"], a["rib_deg"]): np.array(a["force_world_N"])
            for a in source["last_sites"]
        }

    before, after = sites(baseline), sites(current)
    stations = []
    with (
        np.load(previous / case / "shell.npz") as prior,
        np.load(updated / case / "shell.npz") as new,
    ):
        for station in (-12, 12):
            rotkey, centre = f"R{station}", f"C{station}"
            qa, qb = prior[rotkey], new[rotkey]
            holes = []
            for family, radius in (("B", 24.0), ("C", 28.0)):
                for deg in (0, 90, 180, 270):
                    angle = np.radians(deg)
                    hole = radius * np.array([np.cos(angle), np.sin(angle), 0.0])
                    pa, pb = prior[centre] + qa @ hole, new[centre] + qb @ hole
                    holes.append(
                        dict(
                            family=family,
                            azimuth_deg=deg,
                            previous_xyz_mm=pa.tolist(),
                            updated_xyz_mm=pb.tolist(),
                            change_mm=float(np.linalg.norm(pb - pa)),
                        )
                    )

            def near(source):
                s = next(
                    row
                    for row in source["stations"]
                    if row["station"] == station and row["case"] == case
                )
                return s["relieved"]["nearest_unintended"]

            stations.append(
                dict(
                    station_mm=station,
                    station_centre_change_mm=float(
                        np.linalg.norm(new[centre] - prior[centre])
                    ),
                    rotation_change_deg=float(
                        np.degrees(Rotation.from_matrix(qb @ qa.T).magnitude())
                    ),
                    maximum_hole_change_mm=max(h["change_mm"] for h in holes),
                    holes=holes,
                    earlier_closest=near(prev_cad),
                    updated_closest=near(curr_cad),
                    maximum_bearing_force_change_N=max(
                        float(np.linalg.norm(after[k] - before[k]))
                        for k in before
                        if k[0] == station
                    ),
                )
            )
    result = dict(
        hold=int(case),
        scope="One-way transfer of the updated disk pose and 16 simultaneous B/C hole forces into the two inner M5 seats. Guide positions are in the M5 proximal reference frame, in mm. This held-state comparison does not feed the seat response back into the complete rod.",
        stations=stations,
        inputs=current["shared_rod_boundary"],
        peak_hole_change_mm=max(s["maximum_hole_change_mm"] for s in stations),
        peak_bearing_force_change_N=max(
            s["maximum_bearing_force_change_N"] for s in stations
        ),
    )
    (group / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--previous-fields", type=Path, required=True)
    p.add_argument("--updated-fields", type=Path, required=True)
    a = p.parse_args()
    data = compare(a.results, a.previous_fields, a.updated_fields)
    print(data["peak_hole_change_mm"], data["peak_bearing_force_change_N"])
