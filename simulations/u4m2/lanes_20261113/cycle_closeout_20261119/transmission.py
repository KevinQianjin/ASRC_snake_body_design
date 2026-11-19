"""Twelve-rope length closure and directional capstan sensitivity on the actual commanded configurations."""

import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from replay import SHARED, NAMES, plant
from bellmouth_model import sample_span
from shared_bore import solve

COEFFICIENTS = (0.0, 0.05, 0.15, 0.30)


def write_force_envelopes(out, ids, phases, wrap, reference):
    """Write one row per physical rope and pose for the fixed-geometry sensitivity."""
    table = out / "rope_winch_distal_envelopes.csv.gz"
    header = ["step", "phase", "rope", "total_wrap_deg", "nominal_winch_N"]
    bands = []
    for mu in COEFFICIENTS[1:]:
        label = f"mu_{mu:.2f}".replace(".", "p")
        header.extend([f"{label}_distal_low_N", f"{label}_distal_high_N"])
        bands.extend([reference * np.exp(-mu * wrap), reference * np.exp(mu * wrap)])
    groups = {"a4": "A", "a5": "B", "a6": "C"}
    channels = [
        groups[group] + "_" + ray for group, ray in (n.split("_") for n in NAMES)
    ]
    with gzip.open(table, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        for i, (step, phase) in enumerate(zip(ids, phases, strict=True)):
            for j, channel in enumerate(channels):
                writer.writerow(
                    [
                        step,
                        phase,
                        channel,
                        np.degrees(wrap[i, j]),
                        reference[i, j],
                        *(band[i, j] for band in bands),
                    ]
                )


def turns(path):
    delta = np.diff(path, axis=0)
    length = np.linalg.norm(delta, axis=1)
    d = delta[length > 1e-8] / length[length > 1e-8, None]
    theta = np.arctan2(
        np.linalg.norm(np.cross(d[:-1], d[1:]), axis=1), np.sum(d[:-1] * d[1:], axis=1)
    )
    return float(length.sum()), float(theta.sum())


def material_path(rod, detail, pairs, lane, ray):
    """Return world polyline in mm and the rigid material frame carrying each contact."""
    base = rod.base
    p, F, sub = detail["points"], detail["frames"], base.sub
    off = base.offsets3[lane, ray]

    def guide(node):
        return (p[node] + F[node] @ off) * 1000.0

    def through(nodes):
        return np.array([guide(n) for n in nodes]), np.array(nodes)

    def span(body, end):
        node = (body + end) * sub
        near = node + (1 if end == 0 else -1) * sub // 4
        local = F[node].T @ (guide(near) / 1000 - p[node]) - off
        q = sample_span(
            local,
            1 if end == 0 else -1,
            base.bellmouth_profiles[body - 4, end],
            max_step=0.00007,
        )
        world = (p[node] + (q + off) @ F[node].T) * 1000.0
        owners = np.full(len(q), node)
        owners[-1] = near
        return (world, owners) if end == 0 else (world[::-1], owners[::-1])

    pieces = [through([j * sub for j in range(5)])]
    shared_turn = None
    if lane:
        pieces.append(span(4, 0))
        pieces.append(through([4 * sub + n * sub // 8 for n in (2, 3, 5, 6)]))
        if lane == 1:
            pieces.append(span(4, 1))
        else:
            shared, _ = solve(*pairs[ray], rod.profiles, rod.step)
            shared_turn = turns(shared)[1]
            owners = np.full(len(shared), 5 * sub)
            owners[0] -= sub // 4
            owners[-1] += sub // 4
            pieces.append(
                ((p[5 * sub] + (shared / 1000.0 + off) @ F[5 * sub].T) * 1000.0, owners)
            )
            pieces.append(through([5 * sub + n * sub // 8 for n in (2, 3, 5, 6)]))
            pieces.append(span(5, 1))
    closure = max(
        (np.linalg.norm(a[0][-1] - b[0][0]) for a, b in zip(pieces, pieces[1:])),
        default=0.0,
    )
    path = np.vstack([pieces[0][0], *[x[0][1:] for x in pieces[1:]]])
    nodes = np.concatenate([pieces[0][1], *[x[1][1:] for x in pieces[1:]]])
    return path, nodes, closure, shared_turn


def routes(rod, z):
    detail = rod.base.evaluate(z, detail=True)[2]
    pairs = rod.endpoints(z[rod.local])
    lengths = []
    wrap = []
    max_closure = 0.0
    shared_turn = []
    for lane in range(3):
        for ray in range(4):
            path, _, c, shared = material_path(rod, detail, pairs, lane, ray)
            max_closure = max(max_closure, c)
            if shared is not None:
                shared_turn.append(shared)
            ll, ww = turns(path)
            lengths.append(ll)
            wrap.append(ww)
    original = detail["rope_lengths"].copy() * 1000.0
    # Use the independently published rod energy-length calculation for comparison.
    original[2] += rod.correction(z)[0] * 1000.0
    mismatch = np.max(abs(original.ravel() - lengths))
    return np.asarray(wrap), max_closure, float(mismatch), shared_turn


def run(kind, source, out):
    rod, _ = plant()
    key_z, key_t = (
        ("z", "tensions_n") if kind == "holds" else ("motion_z", "motion_tensions_N")
    )
    with np.load(source) as data:
        zs = data[key_z]
        ts = data[key_t].reshape(-1, 12)
        ids = data["hold_id"].astype(int) if kind == "holds" else np.arange(len(zs))
    if kind == "holds":
        with (SHARED / "results/rebalanced_holds.csv").open() as f:
            phases = [r["phase"] for r in csv.DictReader(f)]
    else:
        with gzip.open(source.parent / "motion_trace.json.gz", "rt") as f:
            phases = [r["phase"] for r in json.load(f)]
    if len(zs) != len(ts) or len(zs) != len(phases):
        raise ValueError("Mismatched state, tension or phase records")
    cache = {}
    wraps = []
    worst_close = 0.0
    worst_length = 0.0
    shared = []
    for i, z in enumerate(zs):
        key = z.tobytes()
        if key not in cache:
            cache[key] = routes(rod, z)
        ww, c, ll, turn = cache[key]
        wraps.append(ww)
        shared.append(turn)
        worst_close = max(c, worst_close)
        worst_length = max(ll, worst_length)
        if i % 250 == 0:
            print(kind, i, len(zs), flush=True)
    w = np.stack(wraps)
    rad = np.asarray(shared)
    cols = []
    for mu in COEFFICIENTS:
        low = ts * np.exp(-mu * w)
        high = ts * np.exp(mu * w)
        i, j = np.unravel_index(low.argmin(), low.shape)
        ki, kj = np.unravel_index(high.argmax(), high.shape)
        cols.append(
            dict(
                mu=mu,
                minimum_distal_if_winch_tight_N=float(low[i, j]),
                min_state=int(ids[i]),
                min_phase=phases[i],
                min_rope=NAMES[j],
                maximum_distal_if_winch_pays_N=float(high[ki, kj]),
                max_state=int(ids[ki]),
                max_rope=NAMES[kj],
                records_with_possible_sub_2p5_N=int(np.any(low < 2.5, axis=1).sum()),
                rope_records_with_possible_sub_2p5_N=int((low < 2.5).sum()),
                rope_records_with_possible_above_250_N=int((high > 250).sum()),
            )
        )
    critical = np.divide(
        np.log(ts / 2.5), w, out=np.full_like(w, np.inf), where=w > 1e-10
    )
    i, j = np.unravel_index(critical.argmin(), w.shape)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / f"transmission_{kind}.npz",
        record=ids,
        rope_names=np.array(NAMES),
        total_wrap_rad=w,
        winch_reference_N=ts,
        shared_C_wrap_rad=rad,
    )
    if kind == "motion":
        write_force_envelopes(out, ids, phases, w, ts)
    result = dict(
        states=len(zs),
        unique_geometries=len(cache),
        rope_records=w.size,
        phase_counts={k: phases.count(k) for k in dict.fromkeys(phases)},
        maximum_piece_endpoint_error_mm=worst_close,
        maximum_reconstructed_rope_length_error_mm=worst_length,
        minimum_mu_to_reach_2p5_N=dict(
            mu=float(critical[i, j]),
            state=int(ids[i]),
            rope=NAMES[j],
            phase=phases[i],
            nominal_winch_N=float(ts[i, j]),
            wrap_deg=float(np.degrees(w[i, j])),
        ),
        conditions=cols,
        scope="Frozen geometries and winch-side nominal tensions. Local turns from U-module chords, M guide chords and finite end profiles. Both fully sliding directions are evaluated independently. Actual sticking, friction distribution, internal torsional bending, material wear and closed-loop redistribution are unmeasured.",
    )
    (out / f"transmission_{kind}.json").write_text(json.dumps(result, indent=2) + "\n")
    if worst_close > 1e-6 or worst_length > 0.0003:
        raise ValueError(
            f"Geometric continuity or rod length mismatch: {worst_close}, {worst_length}"
        )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=("holds", "motion"), required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(run(a.kind, a.source, a.out)["conditions"])
