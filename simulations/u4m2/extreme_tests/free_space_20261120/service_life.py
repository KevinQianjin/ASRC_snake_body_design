"""Count continuous variable-amplitude histories, loaded sliding and inverse endurance requirements."""

import argparse
from collections import defaultdict
from pathlib import Path
import numpy as np
from study_context import (
    RESULTS,
    ROUND2,
    NAMES,
    read,
    read_csv,
    motion_rows,
    save,
    write_table,
)
from repeat_block import FILES

SLOPES = (3, 5, 8)


def counted(series):
    """Three-point rainflow with original indices, signed means and residual half cycles."""
    x = np.asarray(series, dtype=float)
    if len(x) < 2:
        return []
    ix = np.r_[0, np.flatnonzero(np.diff(x) != 0) + 1]
    if len(ix) > 2:
        dv = np.diff(x[ix])
        ix = ix[np.r_[True, dv[:-1] * dv[1:] < 0, True]]
    stack = []
    cycles = []

    def pair(a, b, n):
        cycles.append((int(a), int(b), abs(x[a] - x[b]), (x[a] + x[b]) / 2, n))

    for i in ix:
        stack.append(i)
        while len(stack) >= 3:
            a, b, c = stack[-3:]
            if abs(x[c] - x[b]) < abs(x[b] - x[a]):
                break
            if len(stack) == 3:
                pair(a, b, 0.5)
                stack.pop(0)
            else:
                pair(a, b, 1.0)
                del stack[-3:-1]
    for a, b in zip(stack, stack[1:]):
        pair(a, b, 0.5)
    return cycles


def dose(cycles, b):
    return sum(n * (r / 2) ** b for _, _, r, _, n in cycles)


def required(d, b):
    # Amplitude at 1e6 cycles needed for 10,000 copies of one block, Miner D=1.
    return (d * 0.01) ** (1 / b)


def matrix(rows, key):
    return np.array([[float(r[n + key]) for n in NAMES] for r in rows])


def blocks(archive, ext):
    yield "first_open_mission", archive
    if ext:
        a = [r for r in ext if int(r["block"]) == 1]
        b = [r for r in ext if int(r["block"]) == 2]
        if not a or not b or b[-1]["phase"] != "reset":
            raise ValueError("Incomplete two-block simulation")
        yield "first_with_reset", archive + a
        yield "second_with_reset", b
        yield "two_continuous", archive + a + b


def run(service, out):
    archives = motion_rows()
    phase_damage = []
    phasesets = []
    channels = []
    spectra = []
    materials = []
    summary = {}
    wear = []

    def force_row(variant, block, n, end, x, ph, unit, eligible=True):
        cy = counted(x)
        if not cy:
            raise ValueError("Missing reversals")
        np.testing.assert_allclose(
            sum(c[2] * c[4] for c in cy), np.abs(np.diff(x)).sum() / 2, atol=1e-8
        )
        largest = max(cy, key=lambda c: c[2])
        da = {b: dose(cy, b) for b in SLOPES}
        row = dict(
            variant=variant,
            block=block,
            channel=n,
            signal=end,
            unit=unit,
            min_value=min(x),
            max_value=max(x),
            largest_range=largest[2],
            largest_mean=largest[3],
            range_start_phase=ph[largest[0]],
            range_end_phase=ph[largest[1]],
            cycles=sum(c[-1] for c in cy),
        )
        row["endurance_basis"] = (
            "additional second block in continuous history"
            if block == "two_continuous"
            else "standalone history"
        )
        for b in SLOPES:
            row[f"amplitude_power_sum_b{b}"] = da[b] if eligible else None
            row[f"required_A_at_1e6_for_10000_blocks_b{b}"] = (
                required(da[b], b) if eligible and block != "two_continuous" else None
            )
        channels.append(row)
        if eligible and block != "two_continuous":
            contribution = defaultdict(float)
            for i, j, r, _, k in cy:
                for phase in (ph[i], ph[j]):
                    contribution[phase] += 0.5 * k * (r / 2) ** 5
            for phase, value in contribution.items():
                phase_damage.append(
                    dict(
                        variant=variant,
                        block=block,
                        channel=n,
                        signal=end,
                        unit=unit,
                        phase=phase,
                        b5_sum=value,
                        share=value / da[5] if da[5] else 0,
                    )
                )
        if block in ("first_open_mission", "second_with_reset") or (
            variant == "nominal_structure" and block == "first_with_reset"
        ):
            for a, j, r, m, k in cy:
                spectra.append(
                    dict(
                        variant=variant,
                        block=block,
                        channel=n,
                        signal=end,
                        unit=unit,
                        start_row=a,
                        end_row=j,
                        start_phase=ph[a],
                        end_phase=ph[j],
                        range=r,
                        mean=m,
                        count=k,
                    )
                )
        return row, da

    for variant, file in FILES.items():
        arch = read_csv(ROUND2 / "rope_control" / (file + ".csv.gz"))
        has_reset = variant != "endpoint_compensation"
        ext = read_csv(service / (variant + "_extension.csv.gz")) if has_reset else []
        summ = {}
        one = {}
        prior_signs = [0] * len(NAMES)
        for label, rows in blocks(arch, ext):
            pro, dist, slip, drum = [
                matrix(rows, k) for k in ("_prox_N", "_dist_N", "_slip_mm", "_drum_mm")
            ]
            ph = np.array([r["phase"] for r in rows])
            prev = (
                matrix(
                    [next(r for r in reversed(ext) if int(r["block"]) == 1)], "_drum_mm"
                )[0]
                if label == "second_with_reset"
                else drum[0]
            )
            travel = abs(np.diff(drum, axis=0, prepend=prev[None, :]))
            rev = np.zeros_like(slip, dtype=int)
            for j in range(len(NAMES)):
                last = 0
                for i in np.flatnonzero(abs(slip[:, j]) > 1e-7):
                    sign = np.sign(slip[i, j])
                    rev[i, j] = int(last != 0 and sign != last)
                    last = sign
            # Include the preceding nonzero direction when counting reversals across the second-block join.
            if label == "second_with_reset":
                for j in range(len(NAMES)):
                    prior = prior_signs[j]
                    active = np.flatnonzero(abs(slip[:, j]) > 1e-7)
                    if len(active) and prior and prior != np.sign(slip[active[0], j]):
                        rev[active[0], j] += 1
            if label == "first_with_reset":
                prior_signs = [
                    np.sign(v[k[-1]]) if len(k := np.flatnonzero(abs(v) > 1e-7)) else 0
                    for v in slip.T
                ]
            endur = []
            for j, n in enumerate(NAMES):
                for key, x in (("winch", pro[:, j]), ("distal", dist[:, j])):
                    rec, da = force_row(variant, label, n, key, x, ph, "N")
                    if label == "first_with_reset":
                        one[n, key] = da
                    if label == "two_continuous":
                        for b in SLOPES:
                            incr = da[b] - one[n, key][b]
                            rec[f"required_A_at_1e6_for_10000_blocks_b{b}"] = required(
                                max(0, incr), b
                            )
                        endur.append(
                            (rec["required_A_at_1e6_for_10000_blocks_b5"], n, key)
                        )
                    else:
                        endur.append(
                            (rec["required_A_at_1e6_for_10000_blocks_b5"], n, key)
                        )
                wear.append(
                    dict(
                        variant=variant,
                        block=label,
                        rope=n,
                        material_travel_mm=abs(slip[:, j]).sum(),
                        drum_travel_mm=travel[:, j].sum(),
                        sliding_direction_changes=rev[:, j].sum(),
                    )
                )
            err = np.array([float(r["pointing_error_deg"]) for r in rows])
            i, j = np.unravel_index(dist.argmin(), dist.shape)
            below = np.flatnonzero(dist.min(axis=1) < 2.5)
            most = int(abs(slip).sum(0).argmax())
            summ[label] = dict(
                states=len(rows),
                minimum_distal_N=dist[i, j],
                minimum_rope=NAMES[j],
                minimum_phase=ph[i],
                peak_proximal_N=pro.max(),
                below_floor_states=len(below),
                first_floor_step=int(rows[below[0]]["step"]) if len(below) else None,
                first_floor_phase=ph[below[0]] if len(below) else None,
                max_axis_error_deg=err.max(),
                above_pointing_states=int(sum(err > 1)),
                largest_material_travel_mm=abs(slip[:, most]).sum(),
                wear_rope=NAMES[most],
                largest_required_A_b5_N=max(endur),
                largest_drum_travel_mm=travel.sum(0).max(),
            )
            if label == "second_with_reset":
                summ[label]["legs"] = {
                    key: dict(
                        states=int(ids.sum()),
                        minimum_distal_N=dist[ids].min(),
                        peak_proximal_N=pro[ids].max(),
                        states_below_floor=int(sum(dist[ids].min(axis=1) < 2.5)),
                        max_pointing_error_deg=err[ids].max(),
                    )
                    for key, ids in (
                        ("mission", ph != "reset"),
                        ("withdrawn_reset", ph == "reset"),
                    )
                }
                turns = [
                    np.flatnonzero(ph == p)[-1]
                    for p in ("right_out", "left_out", "pitch_up", "pitch_down")
                ]
                summ[label]["four_holds_distal_N_hours"] = {
                    str(minutes): dict(
                        zip(NAMES, dist[turns].sum(axis=0) * minutes / 60, strict=True)
                    )
                    for minutes in (1, 10, 60)
                }
            if label != "two_continuous":
                for phase in dict.fromkeys(ph):
                    ids = np.flatnonzero(ph == phase)
                    for j, n in enumerate(NAMES):
                        phasesets.append(
                            dict(
                                variant=variant,
                                block=label,
                                phase=phase,
                                rope=n,
                                substeps=len(ids),
                                min_distal_N=dist[ids, j].min(),
                                max_distal_N=dist[ids, j].max(),
                                min_winch_N=pro[ids, j].min(),
                                max_winch_N=pro[ids, j].max(),
                                travel_material_mm=abs(slip[ids, j]).sum(),
                                actual_drum_travel_mm=travel[ids, j].sum(),
                                reversal_count=int(rev[ids, j].sum()),
                                below_floor_states=int(sum(dist[ids, j] < 2.5)),
                            )
                        )
        if has_reset:
            bound = read(service / (variant + "_closure.json"))["boundaries"]
            a, b = bound[0], bound[-1]
            summ["successive_reset_end_difference"] = {
                k: np.max(abs(np.subtract(a[x], b[x])))
                for k, x in (
                    ("material_mm", "material_mm"),
                    ("drum_mm", "drum_mm"),
                    ("scaled_state", "state"),
                )
            }
        summary[variant] = summ
    # For the structural reference only, trace back the prescribed withdrawn rod shapes.
    # These fixed-location channels were derived from nominal robot states, before friction replay.
    ref = read_csv(ROUND2 / "fatigue_and_strength/duty_channels.csv.gz")
    stop = max(i for i, r in enumerate(archives) if r["phase"] == "straighten")
    idx = list(range(len(ref))) + list(range(stop, -1, -1))
    ph = np.array([r["phase"] for r in ref] + ["reset_reference"] * (1 + stop))
    for n in ref[0]:
        if not (n.startswith(("U1_", "U2_", "U3_", "U4_", "M5_", "M6_"))):
            continue
        unit = "MPa" if n.endswith("MPa") else "strain_fraction"
        v = np.array([float(ref[i][n]) for i in idx])
        eligible = n != "M5_build_Z_kinematic_strain"
        r, d1 = force_row(
            "nominal_structure",
            "first_with_reset",
            n,
            "fixed_site",
            v,
            ph,
            unit,
            eligible,
        )
        r2, d2 = force_row(
            "nominal_structure",
            "two_continuous",
            n,
            "fixed_site",
            np.tile(v, 2),
            np.tile(ph, 2),
            unit,
            eligible,
        )
        for b in SLOPES:
            r2[f"required_A_at_1e6_for_10000_blocks_b{b}"] = (
                required(max(0, d2[b] - d1[b]), b) if eligible else None
            )
        materials.append(
            dict(
                channel=n,
                unit=unit,
                largest_range=r["largest_range"],
                peak=r["max_value"],
                start_phase=r["range_start_phase"],
                end_phase=r["range_end_phase"],
                required_A_b5=r2["required_A_at_1e6_for_10000_blocks_b5"],
            )
        )
    for file, data in (
        ("endurance_channels", channels),
        ("force_spectra", spectra),
        ("phase_exposure", phasesets),
        ("phase_range_dose", phase_damage),
        ("wear", wear),
    ):
        write_table(out / (file + ".csv.gz"), data)
    save(
        out / "life.json",
        dict(
            variants=summary,
            nominal_structure=materials,
            reference_cycles=1000000,
            target_blocks=10000,
            physical_life_blocks=None,
            physical_life_hours=None,
            measured_mission_duration_s=None,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--service", type=Path, default=RESULTS / "service")
    p.add_argument("--out", type=Path, default=RESULTS / "fatigue")
    a = p.parse_args()
    run(a.service, a.out)
