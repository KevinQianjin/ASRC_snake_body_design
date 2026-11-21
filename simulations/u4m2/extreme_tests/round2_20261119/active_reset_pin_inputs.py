"""Validate and save per-guide-hole loads from an active-reset replay."""

from pathlib import Path

import numpy as np

M5_INNER_STATIONS_MM = (-12, 12)


def capture_active_reset_inputs(rows, states, distal_tensions_N, hole_tags, hole_wrenches_CAD):
    """Build a numeric, non-pickle archive aligned row-for-row with solved replay states.

    ``hole_wrenches_CAD`` contains each rope-guide hole wrench as force (N) and
    moment (N mm), in the CAD axes used by ``guide_loads.record``. It is not a
    web-pin reaction; the shell model must still transfer these loads to the pins.
    """
    rows = list(rows)
    tags = [(str(m), int(z), str(f), str(ray)) for m, z, f, ray in hole_tags]
    n = len(rows)
    if n == 0:
        raise ValueError("At least one accepted equilibrium is required")
    if not tags or len(set(tags)) != len(tags):
        raise ValueError("Guide-hole tags must be non-empty and unique")
    if any(m not in ("M5", "M6") for m, _, _, _ in tags):
        raise ValueError("Unexpected module in guide-hole tags")
    if any(f not in ("A", "B", "C") for _, _, f, _ in tags):
        raise ValueError("Unexpected guide family in guide-hole tags")

    for station in M5_INNER_STATIONS_MM:
        present = {(family, ray) for module, z, family, ray in tags if module == "M5" and z == station}
        rays = {ray for _, ray in present}
        expected = {(family, ray) for family in ("B", "C") for ray in rays}
        if len(rays) != 4 or present != expected:
            raise ValueError(f"M5 station {station:+d} must have B/C loads in four rays")

    states = np.asarray(states, dtype=float)
    distal = np.asarray(distal_tensions_N, dtype=float)
    wrenches = np.asarray(hole_wrenches_CAD, dtype=float)
    if states.ndim < 2 or states.shape[0] != n:
        raise ValueError("State array must have one first-axis entry per accepted row")
    if distal.shape != (n, 3, 4):
        raise ValueError(f"Distal tensions must have shape ({n}, 3, 4), got {distal.shape}")
    if wrenches.shape != (n, len(tags), 2, 3):
        raise ValueError(
            f"Guide-hole wrenches must have shape ({n}, {len(tags)}, 2, 3), got {wrenches.shape}"
        )
    if not (np.isfinite(states).all() and np.isfinite(distal).all() and np.isfinite(wrenches).all()):
        raise ValueError("Active-reset archive contains non-finite numeric values")

    required = ("substep", "step", "phase", "kind", "fraction")
    if any(any(key not in row for key in required) for row in rows):
        raise ValueError("Each replay row must include substep, step, phase, kind and fraction")
    if len({int(row["substep"]) for row in rows}) != n:
        raise ValueError("Replay substep identifiers must be unique")

    module, station, family, ray = zip(*tags, strict=True)
    result = dict(
        substep=np.asarray([row["substep"] for row in rows], dtype=np.int64),
        archive_step=np.asarray([row["step"] for row in rows], dtype=np.int64),
        phase=np.asarray([row["phase"] for row in rows], dtype="U32"),
        kind=np.asarray([row["kind"] for row in rows], dtype="U24"),
        fraction=np.asarray([row["fraction"] for row in rows], dtype=float),
        state=states,
        distal_tensions_N=distal,
        hole_module=np.asarray(module, dtype="U8"),
        hole_station_mm=np.asarray(station, dtype=np.int16),
        hole_family=np.asarray(family, dtype="U4"),
        hole_ray=np.asarray(ray, dtype="U8"),
        hole_wrench_CAD=wrenches,
    )
    return result




def active_m5_candidates(data):
    """Choose replay indices at station-force, station-moment and single-hole peaks."""
    tags = (
        data["hole_module"],
        data["hole_station_mm"],
        data["hole_family"],
        data["hole_ray"],
    )
    picked = {}

    def note(index, reason, value, station):
        index = int(index)
        picked.setdefault(index, []).append(
            dict(reason=reason, station_mm=int(station), magnitude=float(value))
        )

    for station in M5_INNER_STATIONS_MM:
        ids = np.flatnonzero((tags[0] == "M5") & (tags[1] == station))
        if len(ids) != 8:
            raise ValueError(f"Expected eight M5 guide holes at station {station:+d}")
        wrench = data["hole_wrench_CAD"][:, ids]
        resultant = wrench.sum(axis=1)
        force = np.linalg.norm(resultant[:, 0], axis=1)
        moment = np.linalg.norm(resultant[:, 1], axis=1)
        hole_force = np.linalg.norm(wrench[:, :, 0], axis=-1).max(axis=1)
        note(np.argmax(force), "station_force_peak", force.max(), station)
        note(np.argmax(moment), "station_moment_peak", moment.max(), station)
        note(np.argmax(hole_force), "individual_hole_force_peak", hole_force.max(), station)

    return [
        dict(
            index=index,
            substep=int(data["substep"][index]),
            archive_step=int(data["archive_step"][index]),
            phase=str(data["phase"][index]),
            kind=str(data["kind"][index]),
            fraction=float(data["fraction"][index]),
            criteria=reasons,
        )
        for index, reasons in sorted(picked.items())
    ]


def validate_complete_replay(summary, csv_row_count, input_state_count):
    """Reject a stress screen based on a truncated or misaligned mission replay."""
    expected = int(summary.get("expected_substeps", -1))
    accepted = int(summary.get("all_substeps", {}).get("states", -1))
    stopped_at = summary.get("stopped_at")
    if stopped_at is not None:
        raise RuntimeError(f"Mission replay stopped early: {stopped_at}")
    if expected <= 0 or accepted != expected:
        raise RuntimeError(
            f"Mission replay is incomplete: accepted {accepted} of {expected} planned substeps"
        )
    if csv_row_count != expected or input_state_count != expected:
        raise RuntimeError(
            "Replay outputs are misaligned: "
            f"planned={expected}, csv={csv_row_count}, pin_inputs={input_state_count}"
        )


def save_active_reset_inputs(path, rows, states, distal_tensions_N, hole_tags, hole_wrenches_CAD):
    """Write a compressed NPZ that can be loaded with ``allow_pickle=False``."""
    arrays = capture_active_reset_inputs(
        rows, states, distal_tensions_N, hole_tags, hole_wrenches_CAD
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    return path


