"""Re-equilibrate selected fixed-winch holds with lateral C-rope travel at the common M5/M6 interface."""

import argparse
from functools import lru_cache
import hashlib
import shutil
import time
import json
from pathlib import Path

import numpy as np
from numba import njit

from shared_bore import (
    ARCHIVE,
    DESIGN,
    RAYS,
    Body,
    apply_bellmouth,
    audit,
    geometry,
    lanes,
    load_rod,
    load_states,
    solve,
    span_geometry,
)
from spatial_model import SpatialDatabaseRod, refine_seed, rotation
from length_cycle import LengthDrive
from solve_bellmouth_holds import damped_stationary


@njit(cache=True)
def endpoints(z, scale, offsets, length, gu, gw):
    """Same Gauss cell kinematics as the rod, restricted to the two guide intervals and expressed in their shared frame."""
    q = (z / scale).reshape(-1, 4)
    n = len(q)
    F = np.eye(3)
    p = np.zeros(3)
    mid = np.eye(3)
    centre = np.zeros(3)
    for i in range(n):
        phi = np.array([q[i, 0], -q[i, 2], q[i, 1]])
        tangent = np.zeros(3)
        for u, w in zip(gu, gw):
            tangent += w * rotation(phi * u)[0][:, 0]
        p += F @ (tangent * (1 + q[i, 3]) * length)
        F = F @ rotation(phi)[0]
        if i + 1 == n // 2:
            mid = F.copy()
            centre = p.copy()
    out = np.empty((4, 2, 3))
    for k in range(4):
        off = offsets[k]
        out[k, 0] = 1000.0 * (mid.T @ (off - centre) - off)
        out[k, 1] = 1000.0 * (mid.T @ (p + F @ off - centre) - off)
    return out


class SharedRod(SpatialDatabaseRod):
    """Preserve the original rod's other paths, inertia and springs, replacing two C-rope spans."""

    def __init__(self, base, profiles, step):
        self.base = base
        self.profiles = profiles
        self.step = step
        n = base.sub // 4
        c = 5 * base.sub
        self.local = slice(4 * (c - n), 4 * (c + n))
        self.indices = np.arange(self.local.start, self.local.stop)
        self.local_scale = base.scale[self.local]
        self.cached = lru_cache(maxsize=140)(self._correction)

    def __getattr__(self, name):
        return getattr(self.base, name)

    def endpoints(self, z):
        return endpoints(
            z,
            self.local_scale,
            self.base.offsets3[2],
            self.base.l,
            self.base.planar.u,
            self.base.planar.w,
        )

    def _correction(self, key):
        z = np.frombuffer(key, dtype=np.float64)
        pts = self.endpoints(z)
        lengths = np.empty(4)
        end_grad = np.empty((4, 2, 3))
        step = 2e-6
        for i, (left, right) in enumerate(pts):
            _, sol = solve(left, right, self.profiles, self.step)
            num = sol["length_mm"]
            directions = np.array(sol["endpoint_directions"]) * np.array(
                [[-1.0], [1.0]]
            )
            for k, (pt, sign, prof) in enumerate(
                zip((left, right), (-1.0, 1.0), self.profiles)
            ):
                length, gradient, *_ = span_geometry(pt, sign, prof)
                num -= length
                directions[k] -= gradient
            lengths[i] = num / 1000.0
            end_grad[i] = directions
        J = np.empty((4, len(z)))
        for k in range(len(z)):
            dz = np.zeros_like(z)
            dz[k] = step
            dp = (self.endpoints(z + dz) - self.endpoints(z - dz)) / (2 * step)
            J[:, k] = np.einsum("iab,iab->i", end_grad, dp) / 1000.0
        return lengths, J

    def correction(self, z):
        return self.cached(
            np.ascontiguousarray(z[self.local], dtype=np.float64).tobytes()
        )

    def evaluate(self, z, T=None, gravity=9.81, detail=False):
        E, g, d = self.base.evaluate(z, T, gravity, True)
        length, J = self.correction(z)
        if T is not None:
            t = np.asarray(T).reshape(3, 4)[2]
            E += float(t @ length)
            g[self.local] += t @ J
        d["rope_lengths"][2] += length
        return (E, g, d) if detail else (E, g)

    def control_jacobian(self, z):
        J = self.base.control_jacobian(z)
        J[8:12, self.local] += self.correction(z)[1]
        return J

    def hessian(self, z, T):
        H = self.base.hessian(z, T)
        h = 2e-4
        t = np.asarray(T).reshape(3, 4)[2]
        D = np.empty((len(self.indices), len(self.indices)))
        for j, k in enumerate(self.indices):
            step = np.zeros_like(z)
            step[k] = h
            D[:, j] = (
                t @ (self.correction(z + step)[1] - self.correction(z - step)[1])
            ) / (2 * h)
        H[self.local, self.local] += (D + D.T) * 0.5
        return H


def gradient_check(rod, z):
    rng = np.random.default_rng(26)
    delta = np.zeros_like(z)
    d = rng.normal(size=len(rod.indices))
    d /= np.linalg.norm(d)
    delta[rod.local] = d
    t = np.array([2.0, 7.0, 16.0, 3.0])
    _, J = rod.correction(z)
    exact = J @ d
    rows = []
    for h in (2e-4, 8e-5):
        measured = (
            rod.correction(z + h * delta)[0] - rod.correction(z - h * delta)[0]
        ) / (2 * h)
        rows.append(
            dict(
                step=h,
                max_length_gradient_error_m=float(np.max(abs(measured - exact))),
                weighted_energy_gradient_error=float(abs(t @ (measured - exact))),
            )
        )
    return rows


def metrics(rod, z):
    angles, d = rod.base.kinematic_metrics(z)
    head = rod.R0 @ (d["points"][-1] + [0.02, 0, 0])
    return head * 1000.0, np.degrees(angles)


def run(a):
    design, base8, profiles = load_rod()
    if a.cells == 8:
        base = base8
    else:
        base = apply_bellmouth(
            lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, a.cells), design
        )
    rod = SharedRod(base, profiles, a.step)
    drive = LengthDrive(rod)
    drive8 = LengthDrive(base8)
    ss = {
        label: (z, T)
        for label, z, T, m in load_states(ARCHIVE / "equilibria_states.npz")[0]
    }
    original = {
        str(r["state"]): r
        for r in json.loads((ARCHIVE / "summary.json").read_text())["rows"]
    }
    bodies = {
        m: Body(DESIGN / n)
        for m, n in (("M5", "M5_lane_anchorB.stl"), ("M6", "M6_lane_anchorC.stl"))
    }
    a.out.mkdir(exist_ok=True, parents=True)
    cache = {}
    start = time.monotonic()
    source_hash = hashlib.sha256(
        (ARCHIVE / "equilibria_states.npz").read_bytes()
    ).hexdigest()
    for label in list(ss) if a.all else a.cases:
        if a.time_limit is not None and time.monotonic() - start > a.time_limit:
            break
        z0, t0 = ss[label]
        rest = np.array(original[label]["candidate_rest_lengths_mm"]) / 1000.0
        rest = rest.reshape(3, 4)
        reproduction = float(np.max(abs(rest - drive8.inverse(z0, t0))) * 1000.0)
        if reproduction > 1e-5:
            raise ValueError("Published winch command mismatch")
        path = a.out / f"{label}.json"
        field = a.out / f"{label}.npz"
        key = hashlib.sha256(z0.tobytes() + t0.tobytes() + rest.tobytes()).hexdigest()
        # Validate reuse against the current command and the energy gradient of this route.
        prior = None
        if a.resume and path.exists() and field.exists():
            prior = a.out
        elif a.reuse and (a.reuse / f"{label}.npz").exists():
            prior = a.reuse
        if prior is not None:
            old = json.loads((prior / f"{label}.json").read_text())
            if (
                old["status"] != "converged"
                or old["cells_per_module"] != a.cells
                or not np.allclose(
                    rest * 1000, old["rest_lengths_mm"], atol=1e-8, rtol=0
                )
            ):
                raise ValueError(f"Checkpoint has different target {label}")
            if (
                old.get("source_archive_sha256", source_hash) != source_hash
                or old.get("cone_step_mm", a.step) != a.step
            ):
                raise ValueError("Checkpoint provenance mismatch")
            with np.load(prior / f"{label}.npz") as data:
                q = data["z"]
                old_t = data["tensions_N"]
                if (
                    rod.residual(drive.energy(q, rest)[1]) > 2e-8
                    or np.max(abs(drive.force(q, rest) - old_t)) > 1e-6
                ):
                    raise ValueError("Saved state fails the current equilibrium")
            if prior != a.out:
                shutil.copyfile(prior / f"{label}.npz", field)
            old.update(
                source_archive_sha256=source_hash,
                cone_step_mm=a.step,
                input_state_sha256=key,
            )
            path.write_text(json.dumps(old, indent=2) + "\n")
            cache[key] = label
            continue
        if key in cache:
            src = cache[key]
            old = json.loads((a.out / f"{src}.json").read_text())
            old.update(hold=int(label), reused_identical_equilibrium=int(src))
            shutil.copyfile(a.out / f"{src}.npz", field)
            path.write_text(json.dumps(old, indent=2) + "\n")
            continue
        seed = z0 if a.cells == 8 else refine_seed(z0, base8, base)
        if a.seed:
            with np.load(a.seed / f"{label}.npz") as prev:
                seed = (
                    refine_seed(prev["z"], base8, base) if a.cells != 8 else prev["z"]
                )
        exact = geometry(base, seed, t0)
        local = rod.endpoints(seed[rod.local])
        mismatch = float(np.max(abs(local - np.array([exact[k] for k in RAYS]))))
        if mismatch > 1e-8:
            raise ValueError("Local and full rod kinematics disagree")
        checks = gradient_check(rod, seed)
        if max(r["max_length_gradient_error_m"] for r in checks) > 3e-5:
            raise ValueError(f"Directional derivative check failed: {checks}")
        out = dict(
            hold=int(label),
            source_archive_sha256=source_hash,
            input_state_sha256=key,
            cone_step_mm=a.step,
            cells_per_module=a.cells,
            source_cells=8,
            command_max_reconstruction_error_mm=reproduction,
            endpoint_kinematics_error_mm=mismatch,
            gradient_checks=checks,
            rest_lengths_mm=(rest * 1000).tolist(),
        )
        print("starting", a.cells, label, checks, flush=True)
        z, trace, why = damped_stationary(
            rod, t0, seed, max_seconds=a.case_seconds, drive=drive, rest=rest
        )
        out.update(status=why, trace=trace)
        if z is not None:
            t = drive.force(z, rest)
            p0, a0 = metrics(SharedRod(base8, profiles, a.step), z0)
            p1, a1 = metrics(rod, z)
            eigen = drive.stability(z, rest, t)
            results = []
            for i, (left, right) in enumerate(rod.endpoints(z[rod.local])):
                path, sol = solve(left, right, profiles, a.step)
                sol.update(
                    ray=RAYS[i],
                    tension_N=float(t[2, i]),
                    cad=audit(path, RAYS[i], design, bodies),
                    design_margins_deg=(
                        np.degrees(profiles[:, 2]) - sol["exit_angles_deg"]
                    ).tolist(),
                )
                results.append(sol)
            out.update(
                head_world_mm=p1.tolist(),
                head_change_from_archived_8_cell_mm=float(np.linalg.norm(p1 - p0)),
                head_angles_deg=a1.tolist(),
                angle_changes_from_archived_8_cell_deg=(a1 - a0).tolist(),
                tensions_N=t.tolist(),
                max_tension_change_N=float(np.max(abs(t - t0))),
                rope_lengths_mm=(
                    rod.evaluate(z, detail=True)[2]["rope_lengths"] * 1000
                ).tolist(),
                minimum_fixed_winch_tangent_eigenvalue=float(eigen),
                shared_paths=results,
            )
            np.savez_compressed(field, z=z, tensions_N=t)
            cache[key] = label
        (a.out / f"{label}.json").write_text(json.dumps(out, indent=2) + "\n")
        print(
            "finished",
            a.cells,
            label,
            why,
            out.get("head_change_from_archived_8_cell_mm"),
            flush=True,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--cases", nargs="+")
    selection.add_argument("--all", action="store_true")
    p.add_argument("--cells", type=int, choices=[8, 16], default=8)
    p.add_argument("--step", type=float, default=0.15)
    p.add_argument("--seed", type=Path)
    p.add_argument("--case-seconds", type=float, default=280)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--reuse", type=Path)
    p.add_argument("--time-limit", type=float)
    run(p.parse_args())
