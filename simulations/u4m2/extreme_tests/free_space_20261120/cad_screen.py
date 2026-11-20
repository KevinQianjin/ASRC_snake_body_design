"""Intersect real M6 guide/cap/wire meshes with each deformed body and examine the nonlocal adapter envelope."""

import argparse
from pathlib import Path
import fcl
import numpy as np
import trimesh
from study_context import CAD, CANDIDATE, NAMES, RESULTS, read_csv, write_table, save
from free_space import PATHS, coordinates, metrics
from pose_map import axis, correct, equilibrate
from replay import plant
from closed_loop_cycle import FeedbackDrive
from m6_full import coefficients, swept_crop
from m6_socket_screen import (
    PARTS,
    WINDOW,
    load_variant,
    mesh_model,
    refine_axial,
    patch,
)
from u_springs import CAD_TO_ROD
from stations import BODIES, GUIDES, STATIONS
from end_events import check_state
from shared_bore import Body, DESIGN
from common import read
import vtk
import igl


class RopeSurface(Body):
    """Oriented nearest-triangle distance using the same closed CAD and a persistent locator."""

    def __init__(self, path):
        super().__init__(path)
        mesh = trimesh.load_mesh(path)
        if not mesh.is_volume:
            raise ValueError("Oriented closed end CAD required")
        self.vertices = np.asarray(mesh.vertices)
        self.faces = np.asarray(mesh.faces, dtype=np.int64)
        self.tree = igl.AABB()
        self.tree.init(self.vertices, self.faces)
        self.field = vtk.vtkImplicitPolyDataDistance()
        self.field.SetInput(self.poly)

    def signed(self, points):
        distance = np.sqrt(
            self.tree.squared_distance(
                self.vertices, self.faces, np.ascontiguousarray(points)
            )[0]
        )
        # If adjacent points straddle a closed surface, their distances sum to at most
        # the connecting segment length. Query the sign anew wherever a crossing is possible.
        segments = np.linalg.norm(np.diff(points, axis=0), axis=1)
        starts = np.r_[
            0, 1 + np.flatnonzero(distance[:-1] + distance[1:] <= segments + 1e-8)
        ]
        for lo, hi in zip(starts, np.r_[starts[1:], len(points)], strict=True):
            if self.field.FunctionValue(points[lo]) < 0:
                distance[lo:hi] *= -1
        return distance


class Geometry:
    def __init__(self, rod, spacing):
        self.shared = rod
        self.rod = rod.base
        self.ends = {k: RopeSurface(v) for k, v in BODIES.items()}
        self.design = read(DESIGN / "design.json")
        self.bodies = {}
        self.parts = {}
        for name, path in BODIES.items():
            raw = trimesh.load_mesh(path)
            if not raw.is_volume:
                raise ValueError(f"Open body CAD: {name}")
            self.bodies[name] = trimesh.util.concatenate(
                [
                    refine_axial(patch(raw.vertices, raw.faces[k : k + 256]), spacing)
                    for k in range(0, len(raw.faces), 256)
                ]
            )
            for st in STATIONS[name]:
                if name == "M6" and abs(st) == 12:
                    parts = load_variant(CANDIDATE, st)
                else:
                    parts = {
                        p: trimesh.load_mesh(GUIDES / f"{name}_z{st:+}_{p}.stl")
                        for p in PARTS
                    }
                    if not all(m.is_volume for m in parts.values()):
                        raise ValueError(f"Open guide CAD: {name} {st}")
                self.parts[name, st] = parts
        self.fixed = {
            key: {
                p: fcl.CollisionObject(mesh_model(m.vertices, m.faces))
                for p, m in parts.items()
            }
            for key, parts in self.parts.items()
        }
        adapter = trimesh.load_mesh(CAD / "guides_v2/head_adapter.stl")
        self.adapter_radius = np.max(
            np.linalg.norm(adapter.vertices @ CAD_TO_ROD.T, axis=1)
        )
        if not adapter.is_volume:
            raise ValueError("Open adapter CAD")

    def prepare(self, details):
        self.crops = {}
        for (name, st), parts in self.parts.items():
            body = swept_crop(
                self.bodies[name], parts, st, self.rod, details, int(name[1]) - 1
            )
            v = body.vertices
            heights, ix = np.unique(v[:, 2], return_inverse=True)
            self.crops[name, st] = v, body.faces, heights, ix

    def query(self, d, z, T):
        r = {}
        for (name, st), (v, faces, h, ix) in self.crops.items():
            a = coefficients(h, st, self.rod, d, int(name[1]) - 1)[ix]
            x = a[:, 0] + v[:, :1] * a[:, 1] + v[:, 1:2] * a[:, 2]
            body = fcl.CollisionObject(mesh_model(x, faces))
            for p in PARTS:
                solid = self.fixed[name, st][p]
                hit = fcl.collide(
                    body, solid, fcl.CollisionRequest(), fcl.CollisionResult()
                )
                g = (
                    0.0
                    if hit
                    else fcl.distance(
                        body, solid, fcl.DistanceRequest(), fcl.DistanceResult()
                    )
                )
                if g < 0:
                    raise ValueError("Invalid distance after disjoint triangle check")
                r[f"{name}_{st:+}_{p}_mm"] = min(g, WINDOW)
        points = np.vstack([np.zeros(3), d["points"] + [0.02, 0, 0]]) * 1000
        arc = np.r_[0, 20 + np.arange(self.rod.m + 1) * self.rod.l * 1000]
        idx = np.where(arc[-1] - arc[1:] >= 2 * self.rod.diameter * 1000 - 1e-8)[0]
        tip = points[-1]
        u = points[idx + 1] - points[idx]
        v = tip - points[idx]
        t = np.clip(np.sum(u * v, axis=1) / np.sum(u * u, axis=1), 0, 1)
        nearest = np.linalg.norm(v - t[:, None] * u, axis=1)
        r["adapter_nonlocal_gap_lower_bound_mm"] = (
            min(nearest) - self.adapter_radius - 500 * self.rod.diameter
        )
        for e in check_state(self.shared, z, T, self.design, self.ends, {}):
            key = f"{e['module']}_{e['end']}_{e['rope']}"
            r[key + "_rope_gap_mm"] = e["minimum_rope_gap_mm"]
            r[key + "_wrap_margin_deg"] = e["design_margin_deg"]
        return r


def failed_part(r):
    for k, v in r.items():
        if k.endswith("_rope_gap_mm"):
            failed = v < -0.005
        elif k.endswith("_wrap_margin_deg"):
            failed = v < 1.0 - 1e-9
        else:
            failed = v <= 0
        if failed:
            return k
    return None


def passed(r):
    return failed_part(r) is None


def screen_counts(history):
    return dict(
        failed_screen_forward=sum(not v["pass_cad"] for v in history),
        rigid_contact_forward=sum(
            any(
                float(v[k]) <= 0
                for k in v
                if k.endswith(("_guide_mm", "_caps_mm", "_wire_envelope_mm"))
            )
            for v in history
        ),
        rope_gap_fail_forward=sum(
            any(float(v[k]) < -0.005 for k in v if k.endswith("_rope_gap_mm"))
            for v in history
        ),
        wrap_allowance_fail_forward=sum(
            any(float(v[k]) < 1.0 - 1e-9 for k in v if k.endswith("_wrap_margin_deg"))
            for v in history
        ),
        adapter_bound_fail_forward=sum(
            float(v["adapter_nonlocal_gap_lower_bound_mm"]) <= 0 for v in history
        ),
    )


def run(root, spacing, out, names):
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    geo = Geometry(rod, spacing)
    for name in names:
        mode, fixed, _, cap = PATHS[name]
        if read(root / (name + ".json"))["limit_deg"] != cap:
            raise ValueError("Incomplete angle search")
        rows = []
        refines = []
        summary = {}
        table = read_csv(root / (name + ".csv.gz"))
        with np.load(root / (name + "_states.npz")) as f:
            states = f["z"]
        ds = [rod.base.kinematic_metrics(z)[1] for z in states]
        geo.prepare(ds)
        checks = [
            geo.query(d, z, np.array([float(r[n + "_N"]) for n in NAMES]).reshape(3, 4))
            for d, z, r in zip(ds, states, table, strict=True)
        ]
        history = []
        for i, (r, gaps) in enumerate(zip(table, checks, strict=True)):
            ideal = r["pass_ideal"] == "True"
            v = dict(
                path=name,
                index=i,
                leg=r["leg"],
                command_deg=float(r["command_deg"]),
                pass_ideal=ideal,
                pass_cad=passed(gaps),
                **gaps,
            )
            rows.append(v)
            if r["leg"] != "return" and ideal:
                history.append(v)
        last = None
        reject = None
        for v in history:
            if not v["pass_cad"]:
                reject = v
                break
            last = v
        bad_component = None
        if reject:
            bad_component = failed_part(checks[reject["index"]])
        low = last["command_deg"] if last else None
        high = reject["command_deg"] if reject else None
        refine_back = True
        if last and reject:
            idx = last["index"]
            z = states[idx]
            R = (
                np.array([float(table[idx][n + "_command_mm"]) for n in NAMES]).reshape(
                    3, 4
                )
                / 1000
            )
            while abs(high - low) > 1:
                mid = (low + high) / 2
                y, p = coordinates(mode, fixed, mid)
                zz, rr, reason = correct(rod, drive, z, R, axis(y, p))
                tag = metrics(rod, drive, zz, rr, y, p, reason)
                d = rod.base.kinematic_metrics(zz)[1]
                geo.prepare([d])
                g = geo.query(d, zz, drive.force(zz, rr))
                ok = tag["pass_ideal"] and passed(g)
                # Verify the new forward probe recovers the previous accepted commands.
                back = equilibrate(rod, drive, zz, R) if ok else None
                recovered = (
                    bool(back is not None and np.max(abs(back - z)) < 1e-6)
                    if ok
                    else None
                )
                refines.append(
                    dict(
                        path=name,
                        command_deg=mid,
                        out_pass=ok,
                        return_to_previous=recovered,
                        **tag,
                        **g,
                    )
                )
                if ok:
                    low = mid
                    z, R = zz, rr
                    refine_back = refine_back and recovered
                else:
                    high = mid
                    bad_component = reason or (failed_part(g) or tag["reason"])
        prefix = [
            v
            for v in history
            if low is not None
            and abs(v["command_deg"] - history[0]["command_deg"])
            <= abs(low - history[0]["command_deg"]) + 1e-8
        ]
        returning = {
            v["command_deg"]: v
            for v in rows
            if v["path"] == name and v["leg"] == "return"
        }
        back_ok = bool(
            prefix
            and refine_back
            and all(
                v["command_deg"] in returning
                and returning[v["command_deg"]]["pass_cad"]
                and returning[v["command_deg"]]["pass_ideal"]
                for v in prefix
            )
        )
        summary[name] = dict(
            last_contiguous_screened_deg=low,
            first_failed_CAD_deg=high,
            first_CAD_component=bad_component,
            prefix_return_checked=back_ok,
            min_adapter_bound_mm=min(
                g["adapter_nonlocal_gap_lower_bound_mm"] for g in checks
            ),
            minimum_gaps={k: min(g[k] for g in checks) for k in checks[0]},
            cad_rows=len(checks),
            **screen_counts(history),
        )
        print(name, low, high, bad_component, flush=True)
        write_table(out / (name + ".csv.gz"), rows)
        if refines:
            write_table(out / (name + "_probes.csv.gz"), refines)
        save(
            out / (name + ".json"),
            dict(
                spacing_mm=spacing,
                body_faces={k: len(v.faces) for k, v in geo.bodies.items()},
                query_distance_cap_mm=WINDOW,
                adapter_bounding_radius_mm=geo.adapter_radius,
                paths=summary,
            ),
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--angles", type=Path, default=RESULTS / "angles")
    p.add_argument("--out", type=Path, default=RESULTS / "geometry")
    p.add_argument("--spacing", type=float, default=0.5)
    p.add_argument("paths", nargs="*", metavar="PATH")
    a = p.parse_args()
    run(a.angles, a.spacing, a.out, a.paths or PATHS)
