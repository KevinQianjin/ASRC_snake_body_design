"""Build a component-wise sensitivity screen from the archived U4+M2 stress studies.

This script does not recalculate the nonlinear finite-element/rod solutions and
does not infer unmeasured strength. It sweeps explicit trial material limits
against their saved, geometry-specific demands and writes the assumptions into
the output. Run from any directory with Python's standard library only.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Iterable


HERE = Path(__file__).resolve().parent
ROUND2 = HERE / "round2_20261119" / "results"
FREE = HERE / "free_space_20261120" / "results"
DEFAULT_OUT = HERE / "design_limit_sweep_20261122"

PIN_TRIAL_YIELD_MPA = (100, 150, 205, 250, 300, 400, 600, 800)
WEB_TRIAL_STRAIN = (0.005, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.12)
LOAD_FACTORS = (0.5, 1.0, 1.5, 2.0)

GEOMETRY = {
    "Rope plus termination": "12 installed Ø2 mm routes; actual rope/crimp cross-section and termination efficiency unmeasured",
    "M6 adhesive land": "0.5 mm land; current M6 ±12 mm candidate uses a 0.25 mm bond gap",
    "U blade tab": "four NiTi blades per U module; printed PA12 tabs and cage",
    "U NiTi blade": "four NiTi strips per U module; each 94.0 mm long, about 6 mm wide, and 1.03–1.18 mm thick across sampled sections",
    "M5 supported pin and relieved PA12 coupon": "Ø0.60 mm pin; 0.64 mm web hole; 1.50 × 3.00 mm web at the retained seat",
    "M5 remote PA12 web": "1.50 × 3.00 mm web section; eight-rib M5 shell model",
    "M6 adhesive pad": "0.5 mm bonded land with trial G=500 MPa and 0.25 mm bond layer in the archived model",
}

MATERIAL = {
    "Rope plus termination": "Installed rope and crimp materials/lot are unidentified; PA6 solid-stock catalogue data are not a rope strength rating",
    "M6 adhesive land": "PA12 guide with an unqualified adhesive layer; bond modulus and strength are not measured",
    "U blade tab": "Printed PA12 tab/cage reacts superelastic NiTi blades; print orientation and conditioned PA12 strength are unmeasured",
    "U NiTi blade": "Superelastic NiTi; installed lot, transformation response, and fatigue curve are unmeasured",
    "M5 supported pin and relieved PA12 coupon": "Unknown steel pin grade compared with annealed-304 catalogue yield; printed PA12 web has no calibrated local failure law",
    "M5 remote PA12 web": "Printed PA12; build direction, conditioning, and tensile/fracture curve are unmeasured",
    "M6 adhesive pad": "Unqualified adhesive in a trial elastic bond model (G=500 MPa); actual traction and debond law are unknown",
}


def read_json(path: Path):
    return json.loads(path.read_text())


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: Iterable[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    names = list(fields) if fields else (list(rows[0]) if rows else [])
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def first_crossing(rows: list[dict], value_path: tuple[str, ...], threshold: float):
    """Return adjacent sampled states bracketing a threshold, in stored order."""
    previous = None
    for row in rows:
        value = row
        for key in value_path:
            value = value[key]
        value = float(value)
        if value >= threshold:
            return previous, row, value
        previous = row
    return previous, None, None


def stress_component_rows() -> list[dict]:
    source = read_csv(ROUND2 / "fatigue_and_strength" / "required_strength.csv.gz")
    rows = []
    for item in source:
        demand = float(item["upper_sampled_demand"])
        unit = item["unit"]
        for factor in LOAD_FACTORS:
            rows.append(
                {
                    "component": item["component"],
                    "quantity": item["quantity"],
                    "unit": unit,
                    "geometry_basis": GEOMETRY.get(item["component"], "See source basis"),
                    "material_basis": MATERIAL.get(item["component"], "See source basis"),
                    "nominal_peak_demand": demand,
                    "load_factor": factor,
                    "scaled_demand_first_order": demand * factor,
                    "target_resistance_factor_1p5": item["resistance_for_1p5_demand_ratio"],
                    "target_resistance_factor_2p0": item["resistance_for_2p0_demand_ratio"],
                    "measured_lower_bound_resistance": item["measured_lower_bound_resistance"],
                    "rating_status": "UNRATED: no measured lower-bound resistance",
                    "source_basis": item["basis"],
                    "interpretation": "Scaled demand is a first-order sensitivity only; local nonlinear contact, yielding, buckling, and damage can invalidate proportional scaling.",
                }
            )
    return rows


def pin_sweep_rows() -> tuple[list[dict], dict]:
    result = read_json(FREE / "strength" / "pin_area_0.1_fine.json")
    # Keep the neutral seed row: it brackets thresholds already exceeded at 0°.
    pin_rows = result["rows"]
    peak = max(pin_rows, key=lambda r: float(r["peak_pin_bending_MPa"]))
    out = []
    for threshold in PIN_TRIAL_YIELD_MPA:
        before, crossing, _ = first_crossing(pin_rows, ("peak_pin_bending_MPa",), threshold)
        out.append(
            {
                "trial_yield_MPa": threshold,
                "peak_saved_elastic_demand_MPa": peak["peak_pin_bending_MPa"],
                "peak_demand_over_trial_yield": peak["peak_pin_bending_MPa"] / threshold,
                "first_crossing_yaw_deg": crossing["yaw_deg"] if crossing else "",
                "preceding_yaw_deg": before["yaw_deg"] if before else "",
                "status": "crossed on sampled left-out branch" if crossing else "not crossed on sampled left-out branch",
                "geometry": "Ø0.60 mm pin at M5 +12 mm station, 67.5° rib; fine local contact mesh",
                "caveat": "Trial yield threshold; installed pin grade, post-yield law, and rupture strength are unknown. Elastic demand beyond first yield is not a fracture prediction.",
            }
        )
    exact = {
        "trial_yield_MPa": result["reference_yield_MPa"],
        "installed_pin_grade": result["pin_grade"],
        "peak_saved_elastic_demand_MPa": peak["peak_pin_bending_MPa"],
        "peak_yaw_deg": peak["yaw_deg"],
        "first_crossing_bracket": next(
            (
                {
                    "last_below_yaw_deg": row["yaw_deg"],
                    "last_below_MPa": row["peak_pin_bending_MPa"],
                    "first_above_yaw_deg": pin_rows[i + 1]["yaw_deg"],
                    "first_above_MPa": pin_rows[i + 1]["peak_pin_bending_MPa"],
                }
                for i, row in enumerate(pin_rows[:-1])
                if row["peak_pin_bending_MPa"] < result["reference_yield_MPa"]
                <= pin_rows[i + 1]["peak_pin_bending_MPa"]
            ),
            None,
        ),
    }
    return out, exact


def web_sweep_rows() -> list[dict]:
    result = read_json(FREE / "strength" / "pin_area_0.1_fine.json")
    # Keep the neutral seed row: several trial strain thresholds are exceeded
    # before the first outward left-yaw step.
    rows = result["rows"]
    out = []
    for threshold in WEB_TRIAL_STRAIN:
        before, crossing, _ = first_crossing(rows, ("shell_peak_tensile", "strain"), threshold)
        out.append(
            {
                "trial_tensile_strain_percent": 100.0 * threshold,
                "first_crossing_yaw_deg": crossing["yaw_deg"] if crossing else "",
                "preceding_yaw_deg": before["yaw_deg"] if before else "",
                "first_crossing_rib_deg": crossing["shell_peak_tensile"]["rib_deg"] if crossing else "",
                "first_crossing_strain_percent": 100.0 * crossing["shell_peak_tensile"]["strain"] if crossing else "",
                "status": "crossed on sampled left-out branch" if crossing else "not crossed on sampled left-out branch",
                "geometry": "Eight-rib M5 PA12 shell; local peak location can move between ribs",
                "caveat": "Trial strain criterion only. PA12 build direction, conditioning, lot, crack strain, and fracture energy are not calibrated; local peak is mesh-sensitive.",
            }
        )
    return out


def rope_sweep_rows() -> list[dict]:
    return read_csv(FREE / "strength" / "pull_capacity_lookup.csv.gz")


def fatigue_sweep_rows() -> list[dict]:
    source = read_csv(ROUND2 / "fatigue_and_strength" / "endurance_requirements.csv.gz")
    out = []
    for item in source:
        out.append(
            {
                "channel": item["channel"],
                "unit_note": item["interpretation"],
                "governing_range": item["governing_range"],
                "rainflow_cycles_in_one_modeled_mission": item["rainflow_cycles"],
                "required_amplitude_at_1e6_cycles_for_10000_missions_slope3": item["required_A_at_1e6_for_10000_missions_b3"],
                "required_amplitude_at_1e6_cycles_for_10000_missions_slope5": item["required_A_at_1e6_for_10000_missions_b5"],
                "required_amplitude_at_1e6_cycles_for_10000_missions_slope8": item["required_A_at_1e6_for_10000_missions_b8"],
                "measured_endurance_curve": "none in repository",
                "rating_status": "DEMAND ONLY: no calibrated S-N/strain-life/force-life curve",
            }
        )
    return out


def conditional_block_sensitivity() -> list[dict]:
    """Illustrate predicted mission blocks under deliberately hypothetical limits."""
    life = read_json(FREE / "fatigue" / "life.json")
    ref_cycles = int(life["reference_cycles"])
    demand = float(
        life["variants"]["active_matched"]["two_continuous"]["largest_required_A_b5_N"][0]
    )
    out = []
    for assumed_amplitude in (3.0, 5.0, 8.0):
        blocks = 10_000 * (assumed_amplitude / demand) ** 5
        out.append(
            {
                "channel": "C_up rope and termination at winch end",
                "assumed_test_amplitude_N_at_reference_cycles": assumed_amplitude,
                "reference_cycles": ref_cycles,
                "assumed_slope": 5,
                "calculated_mission_blocks": blocks,
                "status": "conditional illustration only; assumed resistance is not measured",
                "required_amplitude_for_10000_blocks_N": demand,
                "formula": "10000 * (assumed endurance amplitude / required amplitude)^5, linear cumulative damage",
            }
        )
    return out


def run(outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    component_rows = stress_component_rows()
    pin_rows, pin_summary = pin_sweep_rows()
    web_rows = web_sweep_rows()
    rope_rows = rope_sweep_rows()
    fatigue_rows = fatigue_sweep_rows()
    conditional_rows = conditional_block_sensitivity()

    write_csv(outdir / "component_stress_sweep.csv", component_rows)
    write_csv(outdir / "pin_yield_sensitivity.csv", pin_rows)
    write_csv(outdir / "web_strain_sensitivity.csv", web_rows)
    write_csv(outdir / "rope_capacity_sensitivity.csv", rope_rows)
    write_csv(outdir / "fatigue_demand.csv", fatigue_rows)
    write_csv(outdir / "conditional_life_sensitivity.csv", conditional_rows)

    limits = read_json(FREE / "strength" / "limits.json")
    duty = read_json(ROUND2 / "fatigue_and_strength" / "duty.json")
    summary = {
        "design": "ASRC U4+M2, 500 g head, six 96 mm modules, twelve Ø2 mm ropes",
        "generated_by": Path(__file__).name,
        "source_studies": [
            "round2_20261119: component service demands and 3405-state duty spectrum",
            "free_space_20261120: local M5 pin/web threshold sweeps and hypothetical rope capacities",
        ],
        "pin_reference": pin_summary,
        "free_space_path_limits": limits["paths"],
        "free_space_trial_web_limits": limits["trial_web_left_out"],
        "normal_duty_rope_resistance_targets": [
            {
                "component": row["component"],
                "demand": float(row["upper_sampled_demand"]),
                "unit": row["unit"],
                "target_for_factor_1p5": float(row["resistance_for_1p5_demand_ratio"]),
                "target_for_factor_2p0": float(row["resistance_for_2p0_demand_ratio"]),
            }
            for row in read_csv(ROUND2 / "fatigue_and_strength" / "required_strength.csv.gz")
        ],
        "fatigue": {
            "target_missions": 10000,
            "reference_cycles": int(read_json(FREE / "fatigue" / "life.json")["reference_cycles"]),
            "measured_mission_duration_s": read_json(FREE / "fatigue" / "life.json")["measured_mission_duration_s"],
            "physical_life_missions": read_json(ROUND2 / "fatigue_and_strength" / "duty.json")["physical_life_missions"],
            "conditional_examples": conditional_rows,
        },
        "coverage_gaps": [
            "No measured lower-bound resistance was recorded for any component in the source strength table.",
            "M6 caps, lockwire, U cage shell, M5 hub/fork retention, M-backbone end bonds, and head/base retention lack calibrated failure laws in these stress results.",
            "No validated crack, plasticity, adhesive debond, fatigue, creep, or wear model establishes ultimate failure or calendar service hours.",
            "First-order load scaling is not a substitute for rerunning contact or nonlinear equilibrium at the scaled load.",
        ],
        "files": [
            "component_stress_sweep.csv",
            "pin_yield_sensitivity.csv",
            "web_strain_sensitivity.csv",
            "rope_capacity_sensitivity.csv",
            "fatigue_demand.csv",
            "conditional_life_sensitivity.csv",
        ],
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    summary = run(args.out)
    print(f"wrote {len(summary['files']) + 1} outputs to {args.out}")
    print(f"M5 reference-yield bracket: {summary['pin_reference']['first_crossing_bracket']}")
    print(f"unmeasured resistance rows: {len(summary['normal_duty_rope_resistance_targets'])}")
    print(f"fatigue channels: {len(read_csv(ROUND2 / 'fatigue_and_strength' / 'endurance_requirements.csv.gz'))}")


if __name__ == "__main__":
    main()
