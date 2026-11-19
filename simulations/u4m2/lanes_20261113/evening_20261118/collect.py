"""Reduce envelope and pinned-seat outputs to summary.json and print the report tables."""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
AREAS = (("0p18", 0.18), ("0p055", 0.055), ("0p025", 0.025))
CASES = ("bend67.5", "bend0", "146", "141", "47", "64")
BT = "land 0.30 mm, clearance 0.15 mm, slope 0.25"
BT10 = "land 0.30 mm, clearance 0.10 mm, slope 0.25"
BTK10 = "land 0.30 mm, clearance 0.15 mm, slope 0.10"
V3A = "V3 bonded land 0.15 mm, slope 1.5"
V3B = "V3 variant land 0.25 mm, slope 1.5"


BT20 = "land 0.30 mm, clearance 0.20 mm, slope 0.25"
ENVELOPES = [(t, a) for t, a in AREAS] + [("pin_r0p30_0p055", 0.055), ("pin_r0p30_0p025", 0.025)]


def envelope():
    out = {}
    for tag, area in ENVELOPES:
        d = json.loads((HERE / f"envelope/envelope_{tag}.json").read_text())
        rows = {}
        for case in CASES:
            r = d["cases"][case][-1]
            L = r["lands"]
            tilt = max(math.hypot(*l["rotation_components_deg_radial_axial_normal"][:2]) for l in L)
            rows[case] = dict(
                fraction=r["fraction"],
                v3_0p15_min_clearance_mm=r["profile_scores"][V3A]["min_clearance_mm"],
                v3_0p25_min_clearance_mm=r["profile_scores"][V3B]["min_clearance_mm"],
                bowtie_candidate_min_clearance_mm=r["bowtie"][BT]["min_clearance_mm"],
                bowtie_candidate_limiting=r["bowtie"][BT],
                bowtie_0p10_land_min_clearance_mm=r["bowtie"][BT10]["min_clearance_mm"],
                bowtie_0p20_land_min_clearance_mm=r["bowtie"][BT20]["min_clearance_mm"],
                bowtie_slope_0p10_min_clearance_mm=r["bowtie"][BTK10]["min_clearance_mm"],
                max_radial_travel_mm=max(l["max_need_radial_mm"] for l in L),
                max_tangential_travel_mm=max(l["max_need_tangential_mm"] for l in L),
                max_total_rotation_deg=max(l["relative_rotation_deg"] for l in L),
                max_inplane_rotation_deg=max(abs(l["rotation_components_deg_radial_axial_normal"][2]) for l in L),
                max_out_of_plane_tilt_deg=tilt,
                max_land_force_N=max(l["force_N"] for l in L),
                max_along_web_force_N=max(abs(l["force_along_web_N"]) for l in L),
                max_perpendicular_force_N=max(abs(l["force_perpendicular_inplane_N"]) for l in L),
                max_tangential_force_N=max(abs(l["force_tangential_N"]) for l in L),
                along_web_force_signs=sorted({int(math.copysign(1, l["force_along_web_N"])) for l in L}),
            )
        out[tag] = dict(max_triangle_area_mm2=area, cases=rows)
    return out


def pins():
    out = {}
    for label, folder in (("band_reference", "pin_seat/band_reference"), ("pin_r0p30", "pin_seat/pin_r0p30")):
        out[label] = {}
        for tag, area in AREAS:
            path = HERE / folder / f"summary_{tag}.json"
            if not path.exists():
                continue
            d = json.loads(path.read_text())
            out[label][tag] = {
                c: dict(
                    completed=v["completed"],
                    local_peak_strain=v["local_peak_strain"],
                    near_pivot_peak_strain=v.get("near_pivot_peak_strain"),
                    applied_couple_Nmm=v["applied_couple_Nmm"],
                    tangent_EI_Nmm2=v["tangent_EI_Nmm2"],
                    max_land_force_N=v["max_land_force_N"],
                    max_relative_rotation_deg=v["max_relative_rotation_deg"],
                    minimum_oriented_area_ratio=v["minimum_oriented_area_ratio"],
                )
                for c, v in d["cases"].items()
            }
    return out


def main():
    env = envelope()
    pin = pins()
    (HERE / "summary.json").write_text(json.dumps(dict(envelope=env, pinned_seat=pin), indent=1) + "\n")
    print("| Case | Mesh | V3 0.15 | V3 0.25 | Bow-tie 0.15/0.25 | Bow-tie 0.10 land | Bow-tie 0.20 land | Rot. total / tilt (deg) | Land F / along-web (N) |")
    for tag, _ in ENVELOPES:
        for c, r in env[tag]["cases"].items():
            print(
                f"| {c} | {tag} | {r['v3_0p15_min_clearance_mm']:+.3f} | {r['v3_0p25_min_clearance_mm']:+.3f} | "
                f"{r['bowtie_candidate_min_clearance_mm']:+.3f} | {r['bowtie_0p10_land_min_clearance_mm']:+.3f} | {r['bowtie_0p20_land_min_clearance_mm']:+.3f} | "
                f"{r['max_total_rotation_deg']:.2f} / {r['max_out_of_plane_tilt_deg']:.2f} | "
                f"{r['max_land_force_N']:.2f} / {r['max_along_web_force_N']:.2f} |"
            )
    for label, rows in pin.items():
        for tag, cases in rows.items():
            for c, v in cases.items():
                ps = v["local_peak_strain"]
                npv = v["near_pivot_peak_strain"] or {}
                print(label, tag, c, f"local {ps['strain']:+.4f} at {ps.get('distance_from_land_centre_mm', 0):.2f} mm", f"near {npv.get('strain', 0):+.4f} at {npv.get('distance_from_land_centre_mm', 0):.2f}",
                      "couple", v["applied_couple_Nmm"], "F", round(v["max_land_force_N"], 2),
                      "rot", round(v["max_relative_rotation_deg"], 2), "area", round(v["minimum_oriented_area_ratio"], 3))


if __name__ == "__main__":
    main()
