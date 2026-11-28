"""Native B-Rep (OpenCASCADE) hub-junction variants of the M6 module for the ring_0/ring_3 hotspot.

Evening 27 Nov 2026, Priority 1 of hub_fillet_20261127/HANDOFF.md.

Source of truth: cad/modules/Medium_Stiffness_96.step (single B-Rep solid). The FE body
cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl equals this STEP rotated by -22.5 deg about z
in the hub region (checked here, max deviation reported). Variants are built on the STEP with exact
OCC operations, then only the material *added* by each variant (B-Rep difference, tessellated) is
rotated into the STL frame and unioned onto the FE lattice, so the lane-anchor features of the FE
body are preserved.

Variants
  fillet_R0p14 : true tangent-continuous BRepFilletAPI fillets (R = 0.14 mm, the largest full-round
                 root that fits the 0.30 mm slot) on every concave edge of the 16 rib/hub pocket roots
                 (8 pockets x 2 hub ends) and their 0.40 mm rim steps.
  fillet_R0p25 : same edge set, R = 0.25 mm (OCC returns a valid solid; recorded for completeness).
  slot_fill    : closes the 0.30 mm side gaps and 0.30 mm end gap between each rib end and its hub
                 socket (box b in [-1.8, 1.8], a in [5.2, 8.31], |z| in [17.97, 19.97] fused to the
                 solid), i.e. the rib end is bonded to the socket walls over the 2.0 mm socket depth.
Outputs: results/brep_variants.json, results/cad/M6_<variant>.step.gz (variant B-Rep STEP, gzip),
results/cad/<variant>_delta_stlframe.stl (added material in the FE frame; the slot_fill one is not committed)
"""
import json, sys, time
from pathlib import Path
import numpy as np
import trimesh
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
from OCP.TopTools import TopTools_IndexedMapOfShape, TopTools_IndexedDataMapOfShapeListOfShape
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.TopoDS import TopoDS
from OCP.ChFi3d import ChFi3d
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.GCPnts import GCPnts_AbscissaPoint

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STEP = ROOT / "cad/modules/Medium_Stiffness_96.step"
FE_STL = ROOT / "cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl"
OUT = HERE / "results"; CAD = OUT / "cad"
STEP_TO_STL_DEG = -22.5
PA12_RHO = 1.01e-3  # g/mm^3 (same as hub_fillet_20261127)


def gz(p):
    import gzip, shutil
    with open(p, "rb") as a, gzip.open(str(p) + ".gz", "wb", 9) as b:
        shutil.copyfileobj(a, b)
    p.unlink()


def load_step(p=STEP):
    if str(p).endswith(".gz") or (not Path(p).exists() and Path(str(p) + ".gz").exists()):
        import gzip, tempfile
        q = Path(str(p) if str(p).endswith(".gz") else str(p) + ".gz")
        tmp = Path(tempfile.mkdtemp()) / q.name[:-3]; tmp.write_bytes(gzip.decompress(q.read_bytes())); p = tmp
    r = STEPControl_Reader(); r.ReadFile(str(p)); r.TransferRoots(); return r.OneShape()


def volume(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()


def n_solids(s):
    m = TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(s, TopAbs_SOLID, m); return m.Size()


def rotz(shape, deg):
    t = gp_Trsf(); t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), np.radians(deg))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def to_trimesh(shape, defl=0.004, path=None, ang=0.25):
    BRepMesh_IncrementalMesh(shape, defl, False, ang, True)
    p = str(path or (OUT / "_tmp.stl")); w = StlAPI_Writer(); w.Write(shape, p)
    m = trimesh.load(p)
    m.export(p)  # rewrite as binary STL
    return m


def concave_pocket_edges(s):
    """Concave edges in the hub-ring_0/ring_3 pocket zone (r 6.5-10 mm, |z| 16-21 mm)."""
    M = TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(s, TopAbs_EDGE, M)
    EF = TopTools_IndexedDataMapOfShapeListOfShape(); TopExp.MapShapesAndAncestors_s(s, TopAbs_EDGE, TopAbs_FACE, EF)
    sel = []
    for i in range(1, M.Size() + 1):
        e = TopoDS.Edge_s(M.FindKey(i)); c = BRepAdaptor_Curve(e)
        P = np.array(c.Value(0.5 * (c.FirstParameter() + c.LastParameter())).Coord())
        r = np.hypot(P[0], P[1])
        if not (6.5 <= r <= 10.0 and 16.0 <= abs(P[2]) <= 21.0):
            continue
        fs = [TopoDS.Face_s(f) for f in EF.FindFromKey(e)]
        if len(fs) != 2:
            continue
        t = str(ChFi3d.DefineConnectType_s(e, fs[0], fs[1], 1e-4, True)).split("_")[-1]
        if t == "Concave":
            sel.append(dict(edge=e, mid=P.tolist(), r=float(r), length=float(GCPnts_AbscissaPoint.Length_s(c))))
    return sel


def fillet(s, edges, R):
    mk = BRepFilletAPI_MakeFillet(s)
    for d in edges:
        mk.Add(R, d["edge"])
    try:
        mk.Build()
    except Exception:
        return None, "exception"
    if not mk.IsDone():
        return None, f"not done ({mk.NbFaultyContours()} faulty contours)"
    return mk.Shape(), "ok"


def slot_fill(s):
    out = s
    for k in range(8):
        phi = np.radians(45.0 * k - 90.0)  # pocket axes of the STEP frame (one at -90 deg)
        for zlo in (-19.97, 17.97):
            box = BRepPrimAPI_MakeBox(gp_Pnt(5.2, -1.8, zlo), 3.11, 3.6, 2.0).Shape()
            box = rotz(box, np.degrees(phi))
            out = BRepAlgoAPI_Fuse(out, box).Shape()
    return out


def main():
    t0 = time.monotonic(); CAD.mkdir(parents=True, exist_ok=True)
    s = load_step(); V0 = volume(s)
    rec = dict(source_step=str(STEP.relative_to(ROOT)), fe_stl=str(FE_STL.relative_to(ROOT)),
               step_volume_mm3=V0, step_valid=bool(BRepCheck_Analyzer(s).IsValid()), variants={})
    # 1. Frame check: STEP rotated by -22.5 deg vs FE STL in the hub region (r < 14, |z| < 30)
    A = to_trimesh(rotz(s, STEP_TO_STL_DEG), 0.01, OUT / "_step_stlframe.stl")
    B = trimesh.load(FE_STL)
    v = B.vertices; m = (np.hypot(v[:, 0], v[:, 1]) < 14) & (np.abs(v[:, 2]) < 30)
    d = np.abs(trimesh.proximity.ProximityQuery(A).signed_distance(v[m]))
    rec["frame_check"] = dict(rotation_deg=STEP_TO_STL_DEG, n_vertices=int(m.sum()),
                              max_dev_mm=float(d.max()), p95_dev_mm=float(np.percentile(d, 95)))
    print("frame check", rec["frame_check"], flush=True)
    edges = concave_pocket_edges(s)
    rec["pocket_concave_edges"] = dict(n=len(edges), families=sorted({(round(e["r"], 2), round(abs(e["mid"][2]), 2), round(e["length"], 2)) for e in edges}))
    print("concave pocket edges", rec["pocket_concave_edges"], flush=True)
    variants = {}
    for R in (0.14, 0.25, 0.30, 0.50, 0.80):
        sh, msg = fillet(s, edges, R)
        variants[f"fillet_R{R:.2f}".replace(".", "p")] = (sh, msg, dict(kind="brep_fillet", R_mm=R))
    sh = slot_fill(s); variants["slot_fill"] = (sh, "ok", dict(kind="slot_fill"))
    for name, (sh, msg, meta) in variants.items():
        info = dict(meta, build=msg)
        if sh is not None:
            info.update(valid=bool(BRepCheck_Analyzer(sh).IsValid()), n_solids=n_solids(sh),
                        volume_mm3=volume(sh), added_volume_mm3=volume(sh) - V0,
                        added_mass_g=(volume(sh) - V0) * PA12_RHO)
            if info["valid"] and info["n_solids"] == 1:
                w = STEPControl_Writer(); w.Transfer(sh, STEPControl_AsIs); w.Write(str(CAD / f"M6_{name}.step"))
                gz(CAD / f"M6_{name}.step")
                delta = BRepAlgoAPI_Cut(sh, s).Shape()
                dm = to_trimesh(rotz(delta, STEP_TO_STL_DEG), 0.004, CAD / f"{name}_delta_stlframe.stl")
                info.update(delta_volume_mm3=float(dm.volume) if dm.is_watertight else None,
                            delta_watertight=bool(dm.is_watertight), delta_faces=int(len(dm.faces)))
        print(name, {k: v for k, v in info.items()}, flush=True)
        rec["variants"][name] = info
    rec["elapsed_s"] = time.monotonic() - t0
    (OUT / "brep_variants.json").write_text(json.dumps(rec, indent=1))
    for p in (OUT / "_tmp.stl", OUT / "_step_stlframe.stl"):
        p.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
