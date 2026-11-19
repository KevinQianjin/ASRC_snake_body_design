"""Solve the coupon's signed, orientation-paired force ramps and compare with the archived contact results."""

import argparse
import json

import numpy as np
from scipy.spatial.transform import Rotation
from cvxopt import solvers
from bench_inputs import (
    COMPONENTS,
    PREVIOUS,
    TARGET_SITES,
    REF_FORCE,
    load_targets,
    program,
    write_csv,
)
from contact import Patch, evaluate
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--level", choices=["middle", "fine", "finer"], default="fine")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    targets = load_targets()
    commands = program(targets)
    write_csv(a.out / "load_program.csv", commands)
    patch = Patch(a.level, 2.7, fit_relief=True)
    rows = []
    for name, (land, F, R) in targets.items():
        for scale in [
            REF_FORCE / np.linalg.norm(F),
            0.25,
            0.5,
            0.75,
            1.0,
            -0.25,
            -0.5,
            -0.75,
            -1.0,
        ]:
            source = land | {key: val * scale for key, val in zip(COMPONENTS, F)}
            result = evaluate(patch, source)
            if not result["converged"] or result["force_residual_N"] > 0.005:
                raise ValueError(f"Unbalanced coupon load {name} {scale}: {result}")
            result.update(
                target=name,
                multiplier=float(scale),
                rotation_coupon_to_pin_xyzw=Rotation.from_matrix(R).as_quat().tolist(),
            )
            rows.append(result)
        print(
            a.level,
            name,
            "at full positive and reversed load",
            [
                (
                    round(x["translation_mm"], 6),
                    round(100 * x["peak_tensile_principal_strain"], 3),
                )
                for x in rows
                if x["target"] == name and abs(x["multiplier"]) == 1
            ],
            flush=True,
        )
    summary = []
    for name, (case, z, theta) in TARGET_SITES.items():
        select = {v["multiplier"]: v for v in rows if v["target"] == name}
        plus = select[1]
        minus = select[-1]
        F = np.array(plus["applied_force_spn_N"])
        unit = F / np.linalg.norm(F)
        t = lambda r: np.array(r["relative_translation_spn_mm"])
        arch = json.loads((PREVIOUS / f"results/contact_fine/{case}.json").read_text())[
            "sites"
        ]
        prior = next(r for r in arch if r["rib_deg"] == theta and r["station_mm"] == z)
        diff = t(minus) - t(plus)
        summary.append(
            dict(
                target=name,
                source_force_N=float(np.linalg.norm(F)),
                tilt_deg=plus["tilt_deg"],
                archived_regular_mesh_translation_mm=prior["translation_mm"],
                forward_translation_mm=plus["translation_mm"],
                reversed_translation_mm=minus["translation_mm"],
                loaded_reversal_travel_mm=float(np.linalg.norm(diff)),
                loaded_reversal_projection_on_force_mm=float(diff @ unit),
                forward_peak_strain=plus["peak_tensile_principal_strain"],
                reverse_peak_strain=minus["peak_tensile_principal_strain"],
                forward_peak_pressure_MPa=plus["peak_nodal_pressure_MPa"],
                reverse_peak_pressure_MPa=minus["peak_nodal_pressure_MPa"],
            )
        )
    obj = dict(
        mesh=a.level,
        feature_fitted=True,
        half_span_mm=2.7,
        head_specification_g=500,
        input_sites=TARGET_SITES,
        sign="Pin-on-web force in fixed (s,p,n) frame; the equal and opposite force is applied to the coupon holder.",
        model="Frictionless elastic web; independent static load levels at prescribed orientation. A zero-load translation is nonunique.",
        peak_pairs=summary,
        load_states=rows,
    )
    (a.out / f"coupon_{a.level}.json").write_text(json.dumps(obj, indent=2) + "\n")


if __name__ == "__main__":
    main()
