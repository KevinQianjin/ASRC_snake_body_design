"""Screen active-reset M5 guide loads through the seat, pin and local contact model."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np
from scipy.spatial.transform import Rotation

from common import LANES, OUT, ROOT, input_file, load_motion, read, read_csv, save
from active_reset_pin_inputs import active_m5_candidates
from m5_seats import conditions, pin_seat, shell, study

sys.path.insert(0, str(LANES / "m5_retained_seat_20261118"))
sys.path.insert(0, str(LANES / "p3_pin_fixture_20261119"))
from inputs import joint
from supported_contact import Interface, Patch, Steel, evaluate, solvers


PIN_MATERIAL_ID = "ss304_annealed"


def verify_station_totals(data, rows):
    """Ensure stored per-hole wrenches reproduce the replay's station-resultant columns."""
    if len(rows) != len(data["substep"]):
        raise ValueError("Replay CSV and active-reset NPZ have different row counts")
    for station, suffix in ((-12, "minus"), (12, "plus")):
        ids = np.flatnonzero(
            (data["hole_module"] == "M5") & (data["hole_station_mm"] == station)
        )
        if len(ids) != 8:
            raise ValueError(f"Expected eight M5 guide holes at station {station:+d}")
        total = data["hole_wrench_CAD"][:, ids].sum(axis=1)
        force = np.linalg.norm(total[:, 0], axis=1)
        moment = np.linalg.norm(total[:, 1], axis=1)
        recorded_force = np.asarray([float(row[f"M5_z{suffix}12_force_N"]) for row in rows])
        recorded_moment = np.asarray([float(row[f"M5_z{suffix}12_moment_Nmm"]) for row in rows])
        np.testing.assert_allclose(force, recorded_force, rtol=1e-9, atol=1e-7)
        np.testing.assert_allclose(moment, recorded_moment, rtol=1e-9, atol=1e-7)


def _load_transfer_frames(model, q, x, force):
    """Add the rib/web-to-pin basis used by the archived P3 contact solver."""
    rows = _original_land_reactions(model, q, x, force)
    for row in rows:
        station = row["station_mm"]
        rib = list(model.mesh.theta).index(row["rib_deg"])
        guide_R = shell.rotation(q[model.bodies[f"G{station:+}"].rot])[0]
        land_R = shell.rotation(q[model.bodies[f"L{rib}_{station}"].rot])[0]
        basis = Rotation.from_euler("z", row["rib_deg"], degrees=True).as_matrix() @ joint.web_axes(station)
        axes = guide_R @ basis
        row["force_spn_N"] = axes.T @ row["force_N"]
        row["coupon_to_pin"] = axes.T @ land_R @ basis
    return rows


_original_land_reactions = study.land_reactions


def _run_shell_candidates(data, candidates, output_dir):
    rod, _, _ = load_motion()
    holes = dict(
        module=data["hole_module"],
        station_mm=data["hole_station_mm"],
        step=data["substep"],
        lane=data["hole_family"],
        direction=data["hole_ray"],
        wrenches=data["hole_wrench_CAD"],
    )
    pin_seat.install(0.30)
    model = shell.Model(shell.Mesh(0.055), "point")
    targets = []
    study.land_reactions = _load_transfer_frames
    try:
        for candidate in candidates:
            index = candidate["index"]
            state = data["state"][index]
            loads = conditions(rod, state, holes, index)
            with TemporaryDirectory() as temp:
                result = study.run_case(
                    model,
                    {index: loads},
                    str(index),
                    0.25,
                    Path(temp) / "solver.json",
                )
            if not result["completed"]:
                raise RuntimeError(f"M5 shell transfer did not converge at substep {index}")
            lands = result["samples"][-1]["lands"]
            for station in (-12, 12):
                local = [land for land in lands if int(land["station_mm"]) == station]
                if not local:
                    raise RuntimeError(f"No pin reactions returned for M5 station {station:+d}")
                land = max(local, key=lambda row: np.linalg.norm(row["force_N"]))
                targets.append(
                    dict(
                        candidate=candidate,
                        station_mm=station,
                        rib_deg=float(land["rib_deg"]),
                        force_N=np.asarray(land["force_spn_N"], dtype=float),
                        coupon_to_pin=np.asarray(land["coupon_to_pin"], dtype=float),
                        force_magnitude_N=float(np.linalg.norm(land["force_N"])),
                    )
                )
            save(
                output_dir / "m5_active_reset_shell_candidates.json",
                [
                    dict(
                        candidate=t["candidate"],
                        station_mm=t["station_mm"],
                        rib_deg=t["rib_deg"],
                        force_spn_N=t["force_N"].tolist(),
                        force_magnitude_N=t["force_magnitude_N"],
                        coupon_to_pin=t["coupon_to_pin"].tolist(),
                    )
                    for t in targets
                ],
            )
    finally:
        study.land_reactions = _original_land_reactions
    return targets


def _contact_state(interface, force, scale):
    state = evaluate(interface, force * scale)
    if not state.get("converged") or state.get("contact_force_residual_N", np.inf) > 1e-4:
        raise RuntimeError(f"Pin/web contact did not converge at load scale {scale:g}")
    return state


def _yield_bracket(interface, force, stress_at_one, limit_mpa):
    if stress_at_one >= limit_mpa:
        low, high = 0.0, 1.0
    else:
        low, high = 1.0, 2.0
        while high <= 16.0:
            state = _contact_state(interface, force, high)
            if state["maximum_clear_shaft_bending_MPa"] >= limit_mpa:
                break
            low, high = high, high * 2.0
        else:
            return dict(status="yield_not_reached_by_16x", lower_scale=16.0, upper_scale=None)
    probes = []
    while high - low > 0.02:
        scale = 0.5 * (low + high)
        state = _contact_state(interface, force, scale)
        stress = float(state["maximum_clear_shaft_bending_MPa"])
        probes.append(dict(load_factor=scale, bending_MPa=stress))
        if stress < limit_mpa:
            low = scale
        else:
            high = scale
    return dict(
        status="yield_bracketed",
        lower_scale=low,
        upper_scale=high,
        lower_safety_factor_to_yield=low,
        upper_safety_factor_to_yield=high,
        reference_yield_MPa=limit_mpa,
        probe_solutions=probes,
    )


def run(out=OUT, estimate=0.15):
    tag = f"takeup_plant_mu{estimate:g}"
    input_path = input_file(out, "rope_control", tag + "_pin_inputs.npz")
    replay_path = input_file(out, "rope_control", tag + ".csv.gz")
    with np.load(input_path, allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    replay_rows = read_csv(replay_path)
    verify_station_totals(data, replay_rows)
    materials = read(ROOT / "data/materials/rope_materials.json")["materials"]
    pin_material = next(m for m in materials if m["id"] == PIN_MATERIAL_ID)
    limit_mpa = float(pin_material["yield_strength_pa"]) * 1e-6
    candidates = active_m5_candidates(data)
    result_dir = out / "m5_structure"
    result_dir.mkdir(parents=True, exist_ok=True)
    targets = _run_shell_candidates(data, candidates, result_dir)

    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    web = Patch("fine", 2.7, fit_relief=True)
    shaft = Steel(0.15, "clamped", 200000.0, -2.57)
    contact_rows = []
    for target in targets:
        interface = Interface(web, shaft, target["coupon_to_pin"], 32)
        at_one = _contact_state(interface, target["force_N"], 1.0)
        contact_rows.append(
            dict(
                candidate=target["candidate"],
                station_mm=target["station_mm"],
                rib_deg=target["rib_deg"],
                transferred_pin_force_N=target["force_magnitude_N"],
                service_bending_MPa=float(at_one["maximum_clear_shaft_bending_MPa"]),
                web_peak_tensile_principal_strain=float(at_one["peak_tensile_principal_strain"]),
                web_p95_volume_tensile_principal_strain=float(at_one["p95_volume_tensile_principal_strain"]),
                web_peak_compressive_principal_strain=float(at_one["most_compressive_principal_strain"]),
                contact_force_residual_N=float(at_one["contact_force_residual_N"]),
                force_spn_N=target["force_N"].tolist(),
                coupon_to_pin=target["coupon_to_pin"].tolist(),
            )
        )
    winner = max(contact_rows, key=lambda row: row["service_bending_MPa"])
    target = next(
        row
        for row in targets
        if row["candidate"] == winner["candidate"]
        and row["station_mm"] == winner["station_mm"]
        and row["rib_deg"] == winner["rib_deg"]
    )
    interface = Interface(web, shaft, target["coupon_to_pin"], 32)
    bracket = _yield_bracket(
        interface,
        target["force_N"],
        winner["service_bending_MPa"],
        limit_mpa,
    )
    summary = dict(
        replay_file=replay_path.name,
        load_file=input_path.name,
        accepted_active_reset_states=int(len(data["substep"])),
        candidate_rule="Peak M5 inner-station force, moment and individual guide-hole force at each station; each candidate transferred through the rotating shell to the worst pin at each loaded station.",
        service_pin_material_scenario=PIN_MATERIAL_ID,
        service_pin_material_is_confirmed=False,
        conditional_yield_reference_MPa=limit_mpa,
        pa12_allowable_is_confirmed=False,
        shell_candidates=candidates,
        contact_cases=contact_rows,
        governing_contact_case=winner,
        conditional_pin_yield_factor=bracket,
        cautions=[
            "This is a screened load-history envelope, not a continuous proof that no unsampled state governs.",
            "The 205 MPa limit is an annealed-304 reference, not the installed pin grade.",
            "The elastic PA12 principal strain is reported but no printable-material allowable is assigned.",
        ],
    )
    save(result_dir / "m5_active_reset_pin_safety.json", summary)
    print(
        "Active-reset M5 pin screen:",
        "states", len(data["substep"]),
        "candidate states", len(candidates),
        "governing substep", winner["candidate"]["substep"],
        "service bending MPa", winner["service_bending_MPa"],
        "conditional yield scale", bracket.get("upper_scale"),
        flush=True,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--estimate", type=float, choices=(0.12, 0.15), default=0.15)
    args = parser.parse_args()
    run(args.out, args.estimate)





