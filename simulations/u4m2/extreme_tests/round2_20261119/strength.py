"""Matched-unit resistance requirements at the specified demand or proof load; physical resistance is unknown."""

import argparse
from pathlib import Path
import numpy as np
from common import input_file, OUT, ROOT, R1, read, read_csv, save, write_table


def run(out):
    rows = []

    def demand(component, metric, unit, value, source):
        rows.append(
            dict(
                component=component,
                quantity=metric,
                unit=unit,
                upper_sampled_demand=value,
                resistance_for_1p5_demand_ratio=1.5 * value,
                resistance_for_2p0_demand_ratio=2 * value,
                measured_lower_bound_resistance=None,
                physical_safety_factor=None,
                basis=source,
            )
        )

    rope = [
        read(input_file(out, "rope_control", "coupled_s0.15_k0.15_b0.1_" + k + ".json"))
        for k in ("open", "feedback", "compensated")
    ]
    proximal = [r["maximum_proximal"][0] for r in rope]
    for estimate in (0.12, 0.15):
        candidate = read(
            input_file(out, "rope_control", f"takeup_plant_mu{estimate:g}.json")
        )
        proximal.append(candidate["all_substeps"]["maximum_proximal_N"][0])
    demand(
        "Rope plus termination",
        "proximal tensile force",
        "N",
        max(proximal),
        "Largest of the three original-step strategies and both free-rod take-up schedules at 500 g",
    )
    m6 = read(input_file(out, "m6_guides", "m6_support.json"))["lands"]
    demand(
        "M6 adhesive land",
        "resultant transmitted at one saddle",
        "N",
        max(np.linalg.norm(v["force_CAD_N"]) for v in m6 if v["gap_mm"] == 0.25),
        "Critical loaded states at the two assumed adhesive moduli, simultaneous load vector",
    )
    u = read(input_file(out, "u_structure", "u_assembly.json"))
    balanced = [r for r in u["cases"] if r["status"] == "balanced"]
    demand(
        "U blade tab",
        "single blade end reaction",
        "N",
        max(b["force_norm_N"] for v in balanced for b in v["blades"]),
        "Three loaded disk states and the sampled axial cage/tab restraint assumptions",
    )
    demand(
        "U NiTi blade",
        "local tensile engineering strain",
        "percent",
        100 * max(b["tension_strain"] for v in balanced for b in v["blades"]),
        "Elastic curved blade model, demand-space strain ratio only",
    )
    m5 = read(input_file(out, "m5_structure", "m5_local.json"))
    for metric, unit in (
        ("p95_volume_tensile_principal_strain", "strain"),
        ("maximum_clear_shaft_bending_MPa", "MPa"),
    ):
        accepted = [
            v for v in m5 if v["converged"] and v["scale"] == 1 and v["mesh"] == "fine"
        ]
        if accepted:
            demand(
                "M5 supported pin and relieved PA12 coupon",
                metric,
                unit,
                max(v[metric] for v in accepted),
                "Fine local contact mesh, two actual motion-step forces in their moving seat frames",
            )
    remote = [read(R1 / f"m5_step_{step}_area_0p055.json") for step in (1843, 2059)]
    demand(
        "M5 remote PA12 web",
        "shell peak principal tensile strain",
        "percent",
        100 * max(v["surface_extremes"]["principal_tensile"]["strain"] for v in remote),
        "Mesh-sensitive remote shell extreme, two actual states at 0.055 square mm element area",
    )
    for v in read_csv(
        input_file(out, "fatigue_and_strength", "endurance_requirements.csv.gz")
    ):
        if v["channel"] == "M6_bond_axial_shear_MPa":
            demand(
                "M6 adhesive pad",
                "absolute axial shear at the fixed maximum-range site",
                "MPa",
                max(abs(float(v["minimum"])), abs(float(v["maximum"]))),
                "Linear trial G=500 MPa and 0.25 mm bond; verify with a joint-level traction law",
            )
    catalog = read(ROOT / "data/materials/rope_materials.json")
    steel = next(m for m in catalog["materials"] if m["id"] == "ss304_annealed")
    upper = max(
        v["maximum_clear_shaft_bending_MPa"]
        for v in m5
        if v["converged"] and v["mesh"] == "fine" and v["scale"] == 1.0
    )
    yield_MPa = steel["yield_strength_pa"] / 1e6
    save(
        out / "m5_structure" / "conditional_pin_factor.json",
        dict(
            material_scenario=steel["id"],
            catalog_role=steel["role"],
            source=steel["property_sources"]["yield_strength_pa"],
            assumed_yield_MPa=yield_MPa,
            highest_service_bending_MPa=upper,
            conditional_bending_yield_ratio=yield_MPa / upper,
            installed_pin_grade=None,
        ),
    )
    proof = []
    for v in m5:
        proof.append(
            {
                k: v.get(k)
                for k in (
                    "step",
                    "mesh",
                    "scale",
                    "converged",
                    "p95_volume_tensile_principal_strain",
                    "peak_tensile_principal_strain",
                    "maximum_clear_shaft_bending_MPa",
                    "peak_nodal_pressure_MPa",
                    "minimum_web_contact_gap_mm",
                    "error",
                )
            }
        )
    write_table(out / "fatigue_and_strength" / "required_strength.csv.gz", rows)
    save(out / "m5_structure" / "proof_loads.json", proof)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
