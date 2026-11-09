"""Full 3D tank clearance screen for U4+M2 with the NiTi backbone.

Replaces the five-width-plane section screen with distance to the triangulated
surface of every solid in the named tank subtree of inputs/tank-v2.step
(external frame excluded, same selection as ../cad_sections.py).

Two checks:
  A. Entry path: the straightened low-strain shape (1 N pretension) translated
     along the installation axis through the bottom opening, as in
     entry_screen.py, but against the full 3D tank.
  B. Held-elevation yaw sweep: every 8-cell state of the minimum-force sweeps
     (min_force_sweep.py) with the clamp held at a fixed insertion depth s.
     Both lateral senses (yaw right and its mirror, yaw left) are checked,
     because the tank is not symmetric about the insertion plane.

Clearance = distance from the front centreline (sampled every <= 2 mm, base
clamp to head) to the tank surface, minus the 31.5 mm radius of the 63 mm
envelope; the head uses the same 63 mm envelope (actual head CAD unknown).
Tank coordinates follow cad_sections.py: length = -oldX, height = oldY,
width = -oldZ (mm). The insertion plane is width 648 mm, the centre of the
2026-11-06 section band; the insertion point is length 449 mm on the cavity
floor profile, as in the 2026-11-06 entry screen.

Limits: rigid tank, no sleeve or guide contact, no rope routing outside the
front, the 63 mm head envelope is provisional, and the front is a quasi-static
equilibrium shape (no dynamics or tolerance). Mesh deflection 0.5 mm.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import sys, json, argparse, time, hashlib
from pathlib import Path
import numpy as np
from backbone import HERE, STUDY, spatial_rod, planar_rod

OUT = HERE / 'results'
CACHE = HERE / '_cache'
STEP = STUDY / 'inputs' / 'tank-v2.step'
PLANE_WIDTH = 648.
R_ENV = 31.5


def tank_mesh(deflection=.5):
    """Triangulate all tank solids once; cache vertices/faces in tank coordinates (mm)."""
    CACHE.mkdir(exist_ok=True)
    sha = hashlib.sha256(STEP.read_bytes()).hexdigest()
    f = CACHE / f'tank_mesh_{sha[:12]}_d{deflection:g}.npz'
    if f.exists():
        d = np.load(f)
        return d['vertices'], d['faces'], sha
    sys.path.insert(0, str(STUDY))
    from cad_sections import load_tank
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    t0 = time.time()
    _, _, parts, _ = load_tank(STEP)
    V, F, n = [], [], 0
    for part in parts:
        shape = part['shape']
        BRepMesh_IncrementalMesh(shape, deflection, False, .5, True)
        ex = TopExp_Explorer(shape, TopAbs_FACE)
        while ex.More():
            face = TopoDS.Face_s(ex.Current()); loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is not None:
                tr = loc.Transformation()
                pts = np.array([[*tri.Node(i).Transformed(tr).Coord()] for i in range(1, tri.NbNodes() + 1)])
                tris = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1
                if face.Orientation() == TopAbs_REVERSED:
                    tris = tris[:, ::-1]
                V.append(pts); F.append(tris + n); n += len(pts)
            ex.Next()
    V = np.vstack(V); F = np.vstack(F)
    V = np.c_[-V[:, 0], V[:, 1], -V[:, 2]]  # length, height, width
    np.savez_compressed(f, vertices=V, faces=F)
    print(f'tank mesh: {len(parts)} parts, {len(F)} triangles, {time.time()-t0:.0f}s', flush=True)
    return V, F, sha


class Tank:
    def __init__(self):
        import trimesh
        V, F, self.sha = tank_mesh()
        self.F = F
        self.mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
        self.query = trimesh.proximity.ProximityQuery(self.mesh)
        prof = np.load(STUDY / 'results/cavity_profiles.npz')
        self.entry_h = float(np.interp(449., prof['length_mm'], prof['floor_mm']))

    def clearance(self, centreline_mm, coarse=20., fine=2.):
        """Exact minimum clearance of the 63 mm envelope around a polyline (tank coords, mm).

        Distance to a fixed surface is 1-Lipschitz along the curve, so after a
        coarse pass (spacing h) the true minimum lies within h/2 of a coarse
        sample whose distance is below (coarse minimum + h). Only those
        neighbourhoods are re-sampled at the fine spacing.
        """
        pc = densify(centreline_mm, coarse)
        _, dc, _ = self.query.on_surface(pc)
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pc, axis=0), axis=1))]
        pf = densify(centreline_mm, fine)
        af = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pf, axis=0), axis=1))]
        near = arc[dc <= dc.min() + coarse]
        mask = np.zeros(len(pf), bool)
        for a0 in near:
            mask |= np.abs(af - a0) <= coarse
        _, df, _ = self.query.on_surface(pf[mask])
        i = int(np.argmin(df)); pt = pf[mask][i]
        return float(df[i] - R_ENV), pt, float(af[mask][i] / max(af[-1], 1e-9))


def densify(p, step):
    out = [p[:1]]
    for a, b in zip(p[:-1], p[1:]):
        k = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out.append(a + (b - a) * (np.arange(1, k + 1)[:, None] / k))
    return np.vstack(out)


def to_tank(world_mm, pitch, s, entry_h, side=+1):
    """Front world coords (X forward, Y up, Z right; origin at base clamp) -> tank (length, height, width)."""
    a = np.radians(pitch)
    base = np.array([449. + s * np.cos(a), entry_h + s * np.sin(a)])
    return np.c_[base[0] + world_mm[:, 0], base[1] + world_mm[:, 1], PLANE_WIDTH + side * world_mm[:, 2]]


def entry_path(tank, variant, pitch):
    """A: straight 1 N-pretension shape translated along the axis, full 3D tank."""
    from run_sweep import score, COARSE_BOUND
    from refine_front import finer_seed
    r = planar_rod(4, 2, [4, 5, 6], pitch, 4, variant, common=1.)
    rec = json.loads((OUT / 'pretension1_recheck.json').read_text())
    D = np.array(next(q for q in rec if q['variant'] == variant and q['pitch_deg'] == pitch)['top_extra_tensions_n'])
    x = r.solve_ramped(D, r.straight_seed())
    f = planar_rod(4, 2, [4, 5, 6], pitch, 8, variant, common=1.)
    xf = f.solve_ramped(D, finer_seed(x, r, f))
    _, p2, _ = f.metrics(xf, D)
    world = np.c_[p2 * 1000, np.zeros(len(p2))]
    L = f.nominal_length * 1000
    ss = np.arange(-L - 150, 400.001, 4.)
    gaps = []
    for s in ss:
        g, pt, frac = tank.clearance(to_tank(world, pitch, s, tank.entry_h))
        gaps.append((s, g, frac, pt))
    return ss, np.array([g[1] for g in gaps]), gaps


def sweep_states(tank, run, variant, pitch, anchors, depths):
    """B: held-elevation sweep states at fixed clamp depth s, both lateral senses."""
    st = np.load(OUT / f'{run}_states.npz')
    r = spatial_rod(4, 2, anchors, pitch, 8, variant)
    rows = []
    keys = sorted([k for k in st.files if k.endswith('_z8')], key=lambda k: float(k[1:-3]))
    for k in keys:
        yaw = float(k[1:-3]); z = st[k]; T = st[k.replace('_z8', '_T8')]
        m, d, world = r.metrics(z, T)
        world = world * 1000
        for s in depths:
            for side in (+1, -1):
                g, pt, frac = tank.clearance(to_tank(world, pitch, s, tank.entry_h, side))
                rows.append(dict(run=run, yaw_deg=yaw, side='right' if side > 0 else 'left', clamp_s_mm=float(s),
                                 clearance_mm=g, critical_point_mm=pt.tolist(), critical_arclength_fraction=frac,
                                 head_tank_mm=to_tank(world[-1:], pitch, s, tank.entry_h, side)[0].tolist(),
                                 peak_n=float(np.max(T))))
    return rows


RUNS = [('minforce_niti18_E40_p20_a456_pre1_exact_smooth1', 'niti18_E40', 20, [4, 5, 6]),
        ('minforce_niti18_E75_p20_a456_pre1_exact_smooth1', 'niti18_E75', 20, [4, 5, 6]),
        ('minforce_niti18_E40_p25_a456_pre1_exact', 'niti18_E40', 25, [4, 5, 6])]


def main(what, run_index, depths):
    tank = Tank()
    print(f'tank mesh: {len(tank.F)} triangles; entry floor height {tank.entry_h:.1f} mm', flush=True)
    if what == 'entry':
        # A: entry paths in full 3D (2D section values were 44 / 64 / 17 mm).
        result = dict(step_sha256=tank.sha, plane_width_mm=PLANE_WIDTH, envelope_radius_mm=R_ENV, entry={})
        for pitch in [15, 20, 25]:
            ss, g, recs = entry_path(tank, 'niti18_E40', pitch)
            i = int(np.argmin(g))
            result['entry'][str(pitch)] = dict(s_mm=ss.tolist(), clearance_mm=g.tolist(), min_clearance_mm=float(g.min()),
                                               s_at_min_mm=float(ss[i]), critical_point_mm=recs[i][3].tolist(),
                                               critical_arclength_fraction=recs[i][2])
            print(f'entry {pitch} deg: 3D min clearance {g.min():.1f} mm at s = {ss[i]:.0f} mm, point {np.round(recs[i][3])}', flush=True)
        (OUT / 'tank3d_entry.json').write_text(json.dumps(result, indent=1, default=float))
    else:
        run, v, p, anch = RUNS[run_index]
        rows = sweep_states(tank, run, v, p, anch, depths)
        for s in depths:
            for side in ['right', 'left']:
                rr = [q for q in rows if q['clamp_s_mm'] == s and q['side'] == side]
                ok = [q for q in rr if q['clearance_mm'] >= 5]
                worst = min(rr, key=lambda q: q['clearance_mm'])
                print(f"{run} s={s:.0f} {side:5s}: {len(ok)}/{len(rr)} states clear (>=5 mm); worst {worst['clearance_mm']:.1f} mm "
                      f"at yaw {worst['yaw_deg']:.0f}, point {np.round(worst['critical_point_mm'])}", flush=True)
        tag = '' if depths == [90, 200, 300] else '_s' + '_'.join(f'{d:g}' for d in depths)
        (OUT / f'tank3d_sweep_{run}{tag}.json').write_text(json.dumps(dict(step_sha256=tank.sha, rows=rows), indent=1, default=float))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('what', choices=['entry', 'sweep'])
    ap.add_argument('--run', type=int, default=0, help='index into RUNS for the sweep check')
    ap.add_argument('--depths', type=float, nargs='+', default=[90, 200, 300])
    a = ap.parse_args(); main(a.what, a.run, a.depths)
