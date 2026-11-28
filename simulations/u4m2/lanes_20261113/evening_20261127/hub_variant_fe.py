"""q3 (and optional q2.5) hub-strain FE of the native B-Rep hub variants (evening 27 Nov 2026).

Reuses hub_fillet_20261127/fillet_study.evaluate_candidate unchanged (CAD sleeve NiTi backbone,
L = 66 mm, G = 500 MPa bond layer, crown 0.06 mm, steps 1709/1869/1884). The only change is the
geometry: the B-Rep-derived added material (results/cad/<variant>_delta_stlframe.stl) is unioned
onto the same cropped FE lattice (body_solid.lattice()).
Usage: python3.13 hub_variant_fe.py baseline slot_fill            (q3/a0.40)
       python3.13 hub_variant_fe.py --q25 baseline                   (q2.5/a0.25)
       python3.13 hub_variant_fe.py --level q3_a025 3.0 0.25 slot_fill (custom level)
"""
import json, sys, time
from pathlib import Path
import numpy as np, trimesh, manifold3d
HERE = Path(__file__).resolve().parent
HF = HERE.parent / "hub_fillet_20261127"
sys.path.insert(0, str(HF))
import fillet_study as FS  # noqa: E402  (adds the evening_2026112x paths)
BS, BF, EV25 = FS.BS, FS.BF, FS.EV25
OUT = HERE / "results"
SHS = FS.SHS
_analyze = SHS.analyze_step


def analyze_step_sites(B, Kt_bare, K_cad, Ul):
    """archived analyze_step + three named sites per hub end (element centroid masks):
    slot_root  : r 7.5-8.8 mm, |z| 17.5-18.6 mm (rib/socket 0.30 mm slot root, baseline ring_0 corner peak)
    arch_crown : r 8.9-11.0 mm, |z| 19.98-21.5 mm (concave arch crown below the socket bottom face)"""
    out = _analyze(B, Kt_bare, K_cad, Ul)
    from strain_check import element_strain
    u = (B.T @ Ul[:B.n]).reshape(-1, 3)
    eps, _ = element_strain(B.X, B.conn, u)
    peak = np.abs(np.linalg.eigvalsh(eps)).max(1)
    c = B.X[B.conn[:, :4]].mean(1); r = np.hypot(c[:, 0], c[:, 1]); az = np.abs(c[:, 2])
    Xv = B.X[B.conn[:, :4]]; vol = np.abs(np.linalg.det(Xv[:, 1:] - Xv[:, :1])) / 6.0
    for end, sgn in (("ring0", -1), ("ring3", 1)):
        side = np.sign(c[:, 2]) == sgn
        out[f"slot_root_{end}"] = SHS.region_strain_metrics(B, eps, peak, c, r, vol, side & (r >= 7.5) & (r <= 8.8) & (az >= 17.5) & (az <= 18.6))
        out[f"arch_crown_{end}"] = SHS.region_strain_metrics(B, eps, peak, c, r, vol, side & (r >= 8.9) & (r <= 11.0) & (az >= 19.98) & (az <= 21.5))
    return out


SHS.analyze_step = analyze_step_sites


# Slot fill, exact B-Rep pocket dimensions (Medium_Stiffness_96.step): socket inner wall a = 5.2 mm,
# socket-wall end a = 8.30722577 mm (r = 8.5 rim), half-width b = 1.8 mm, ceiling |z| = 17.970314267 mm,
# open bottom face |z| = 19.970314267 mm. The FE fill overlaps the solid ceiling and inner wall by
# SLOT_EPS_MM and stops SLOT_OPEN_GAP_MM short of the two open faces (bottom, rim) so that no
# near-coincident faces are created (a 0.05 mm lip groove remains there: slightly conservative).
SLOT_A0, SLOT_A1, SLOT_HALF_B, SLOT_Z0, SLOT_Z1 = 5.2, 8.30722577, 1.8, 17.970314267, 19.970314267
SLOT_EPS_MM, SLOT_OPEN_GAP_MM = 0.02, 0.05


def occ_slot_fill(base):
    """Double-precision OpenCASCADE union of the FE lattice with the 16 pocket fill boxes."""
    from OCP.StlAPI import StlAPI_Reader, StlAPI_Writer
    from OCP.TopoDS import TopoDS_Shape, TopoDS
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.TopTools import TopTools_ListOfShape
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax1, gp_Dir
    tmp = OUT / "_lattice.stl"; base.export(tmp)
    sh = TopoDS_Shape(); StlAPI_Reader().Read(sh, str(tmp))
    sw = BRepBuilderAPI_Sewing(1e-6); sw.Add(sh); sw.Perform()
    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(TopExp_Explorer(sw.SewedShape(), TopAbs_SHELL).Current())).Solid()
    tools = TopTools_ListOfShape()
    a0, a1 = SLOT_A0 - SLOT_EPS_MM, SLOT_A1 - SLOT_OPEN_GAP_MM
    h = (SLOT_Z1 - SLOT_OPEN_GAP_MM) - (SLOT_Z0 - SLOT_EPS_MM)
    for k in range(8):
        phi = np.radians(45.0 * k - 90.0 - 22.5)  # STEP pocket axis rotated into the FE STL frame
        for zlo in (-(SLOT_Z1 - SLOT_OPEN_GAP_MM), SLOT_Z0 - SLOT_EPS_MM):
            box = BRepPrimAPI_MakeBox(gp_Pnt(a0, -SLOT_HALF_B, zlo), a1 - a0, 2 * SLOT_HALF_B, h).Shape()
            tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), phi)
            tools.Append(BRepBuilderAPI_Transform(box, tr, True).Shape())
    args = TopTools_ListOfShape(); args.Append(solid)
    fu = BRepAlgoAPI_Fuse(); fu.SetArguments(args); fu.SetTools(tools); fu.SetFuzzyValue(1e-5); fu.Build()
    assert fu.IsDone()
    r = fu.Shape(); BRepMesh_IncrementalMesh(r, 0.01, False, 0.25, True); StlAPI_Writer().Write(r, str(tmp))
    tm = trimesh.load(tmp); tmp.unlink(missing_ok=True)
    v = np.asarray(tm.vertices, float).copy()
    v[np.abs(v[:, 2] - BS.Z_LO) < 1e-4, 2] = BS.Z_LO
    v[np.abs(v[:, 2] - BS.Z_HI) < 1e-4, 2] = BS.Z_HI
    return trimesh.Trimesh(vertices=v, faces=tm.faces, process=False)


ZONE_R, ZONE_Z = 10.5, (15.5, 21.5)  # hub-pocket splice zones (r < 10.5 mm, 15.5 < |z| < 21.5 mm)


def zone_shapes():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    return [BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z0), gp_Dir(0, 0, 1)), ZONE_R, ZONE_Z[1] - ZONE_Z[0]).Shape()
            for z0 in (-ZONE_Z[1], ZONE_Z[0])]


def spliced_zone_mesh(name):
    """OCC: (variant STEP) intersect (two hub zones), rotated into the FE STL frame, tessellated."""
    import brep_hub_variants as H
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    src = H.STEP if name == "step_splice_control" else H.CAD / f"M6_{name}.step"
    sh = H.load_step(src)
    parts = []
    for z in zone_shapes():
        c = BRepAlgoAPI_Common(sh, z).Shape()
        parts.append(H.to_trimesh(H.rotz(c, H.STEP_TO_STL_DEG), 0.004, OUT / "_zone.stl"))
    (OUT / "_zone.stl").unlink(missing_ok=True)
    return parts


def mf_of(tm):
    return FS.trimesh_to_manifold(tm)


def build(name):
    base, crop = BS.lattice()
    if name == "baseline":
        tm = base
    elif name == "slot_fill":
        tm = occ_slot_fill(base)
    else:
        Mb = mf_of(base)
        for sgn in (-1, 1):
            cyl = manifold3d.Manifold.cylinder(ZONE_Z[1] - ZONE_Z[0], ZONE_R, ZONE_R, 256).translate(
                (0, 0, ZONE_Z[0] if sgn > 0 else -ZONE_Z[1]))
            Mb = Mb - cyl
        parts = [Mb] + [mf_of(p) for p in spliced_zone_mesh(name)]
        mf = manifold3d.Manifold.batch_boolean(parts, manifold3d.OpType.Add)
        mm = mf.to_mesh()  # keep manifold3d's topology; trimesh process=True merges sub-micron slivers
        tm = trimesh.Trimesh(np.asarray(mm.vert_properties[:, :3], float), np.asarray(mm.tri_verts, np.int64), process=False)
        v = np.asarray(tm.vertices, float).copy()
        v[np.abs(v[:, 2] - BS.Z_LO) < 1e-4, 2] = BS.Z_LO
        v[np.abs(v[:, 2] - BS.Z_HI) < 1e-4, 2] = BS.Z_HI
        tm = trimesh.Trimesh(vertices=v, faces=tm.faces, process=False)

    v = tm.vertices; r = np.hypot(v[:, 0], v[:, 1]); z = v[:, 2]
    bore = {f"ring_{i}": float(r[(z >= lo) & (z <= hi) & (r < 6.0)].min()) for i, (lo, hi) in enumerate(BS.RING_Z)}
    info = dict(variant=name, is_watertight=bool(tm.is_watertight), body_count=int(tm.body_count),
                base_volume_mm3=float(base.volume), volume_mm3=float(tm.volume),
                added_volume_mm3=float(tm.volume - base.volume), added_mass_g=float((tm.volume - base.volume) * FS.PA12_DENSITY_G_PER_MM3),
                bore_min_radius_mm=bore, bore_preserved_8p40mm=all(abs(x - 4.20) < 0.01 for x in bore.values()),
                clamped_surface_verts=int((np.abs(z - BS.Z_LO) < 1e-6).sum()), d1_surface_verts=int((np.abs(z - BS.Z_HI) < 1e-6).sum()),
                faces=int(len(tm.faces)), splice_zone=dict(r_max_mm=ZONE_R, abs_z_mm=list(ZONE_Z)),
                min_edge_mm=float(tm.edges_unique_length.min()))
    assert info["is_watertight"] and info["body_count"] == 1 and info["bore_preserved_8p40mm"], info
    return tm, info


def main(argv):
    if "--level" in argv:  # --level <label> <q> <a> <variant...>: one custom mesh level per variant
        i = argv.index("--level"); lab, q, a = argv[i + 1], float(argv[i + 2]), float(argv[i + 3]); names = argv[i + 4:]
        return run(names, [(lab, q, a)])
    q25 = set(argv[argv.index("--q25") + 1:]) if "--q25" in argv else set()
    names = argv[:argv.index("--q25")] if "--q25" in argv else argv
    for name in names + sorted(q25 - set(names)):
        levels = ([("q3_a040", 3.0, 0.40)] if name in names else []) + ([("q2p5_a025", 2.5, 0.25)] if name in q25 else [])
        run([name], levels)


def run(names, levels):
    S = np.load(EV25 / "results/rod_steps.npz")
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    rhs15 = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]
    K_cad, _ = BF.sleeve_backbone_stiffness_d1()
    for name in names:
        t0 = time.monotonic(); st = FS.stamp()
        tm, info = build(name)
        print(f"=== {name}: {info}", flush=True)
        rec = FS.evaluate_candidate(name, tm, info, S, Cb, rhs15, K_cad, levels)
        rec.update(started_et=st["et"], started_utc=st["utc"], completed_et=FS.stamp()["et"], completed_utc=FS.stamp()["utc"], elapsed_s=time.monotonic() - t0)
        tag = "_".join(l[0] if l[0] not in ("q3_a040", "q2p5_a025") else l[0].split("_")[0] for l in levels)
        (OUT / f"fe_{name}_{tag}.json").write_text(json.dumps(rec, indent=1, default=float))
        print(f"saved fe_{name}_{tag}.json in {time.monotonic()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
