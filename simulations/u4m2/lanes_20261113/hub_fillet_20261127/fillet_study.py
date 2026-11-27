"""Stage 2: Watertight hub/arm fillet CAD candidates and FE evaluation (R = 0.8 mm and R = 1.2 mm).

Builds two watertight CAD fillet candidates on M6_lane_anchorC.stl via exact manifold3d boolean
union, targeting both confirmed hotspots from Stage 1 (sleeve_hub_strain.py):
  - ring_0 / ring_3 hub-ring outer junction (r = 8.46 mm, z = +-18.01 mm; baseline peak 3.84-3.89%)
  - ring_1 / ring_2 arm-root junction (r = 11.97 mm, z = +-5.20 mm; baseline peak 3.24%, g0.5 = 1.38%)

Each candidate adds smooth revolved concave-flared collars around the four hub rings (strictly
within r in [4.30, 12.6] mm), preserving the Ø8.40 mm central bore (r = 4.200 mm) and all guide
sockets/lands (r > 13.5 mm). Verifies watertightness, single connected body, bore clearance,
volume/mass delta, equivalent EI change, and q3 / q2.5 hub-strain reduction at steps 1709 / 1869.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import manifold3d
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
EV26 = HERE.parent / "evening_20261126"
MORN26 = HERE.parent / "morning_20261126"
EV25 = HERE.parent / "evening_20261125"
EV24 = HERE.parent / "evening_20261124"
for p in (HERE, EV26, MORN26, EV25, EV24):
    sys.path.insert(0, str(p))

import backbone_strain as MB  # noqa: E402
import body_bond as BB  # noqa: E402
import body_solid as BS  # noqa: E402
import bore_fe as BF  # noqa: E402
import sleeve_hub_strain as SHS  # noqa: E402

OUT = HERE / "results"
PA12_DENSITY_G_PER_MM3 = 1.01e-3  # g/mm^3


def stamp():
    now = datetime.now(timezone.utc)
    return dict(
        et=now.astimezone(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def revolved_collar(r_in, r_out, z_lo, z_hi, flare_z, flare_r, n_arc=6, n_seg=64):
    """Build a watertight revolved hub-ring collar with smooth concave quarter-circle axial flares.
    Profile in (r, z) stays strictly >= r_in (so central bore r=4.20 mm is never touched).
    """
    pts = []
    # Bottom inner corner
    pts.append((r_in, z_lo))
    # Bottom outer flare: from (r_out + flare_r, z_lo) curving smoothly to (r_out, z_lo - flare_z)?
    # Better: flare OUTWARD in r toward ring faces and smoothly taper in r over [z_lo - flare_z, z_lo]
    # Concave fillet profile:
    #   z in [z_lo - flare_z, z_lo]: r(t) = r_out + flare_r * (1 - sin(t)), z(t) = z_lo - flare_z * cos(t), t in [0, pi/2]
    # Wait: at t=0 -> (r_out + flare_r, z_lo - flare_z)? No, we want widest at ring face z_lo and tapering to r_out away from ring!
    # At t=0: (r_out, z_lo - flare_z); at t=pi/2: (r_out + flare_r, z_lo) with smooth tangent!
    # Concave arc center at (r_out + flare_r, z_lo - flare_z):
    #   r(th) = (r_out + flare_r) - flare_r * cos(th), z(th) = (z_lo - flare_z) + flare_z * sin(th)?
    # Check: th=0 -> (r_out, z_lo - flare_z); th=pi/2 -> (r_out + flare_r, z_lo). Wait that's convex.
    # For CONCAVE: center at (r_out + flare_r, z_lo - flare_z) with th from pi/2 down to 0?
    # Let's check: we want r = r_out at z = z_lo - flare_z, and r = r_out + flare_r at z = z_lo,
    # staying INSIDE the straight line (concave):
    #   u in [0, 1]: z = z_lo - flare_z * (1 - u), r = r_out + flare_r * (1 - sqrt(1 - u^2))
    # Check: u=0 -> (r_out, z_lo - flare_z); u=1 -> (r_out + flare_r, z_lo); at u=0.5 -> r = r_out + 0.134*flare_r (concave!).
    pts = [(r_in, z_lo - flare_z)]
    for u in np.linspace(0.0, 1.0, n_arc):
        z = z_lo - flare_z * (1.0 - u)
        r = r_out + flare_r * (1.0 - math.sqrt(max(0.0, 1.0 - u * u)))
        pts.append((r, z))
    # Top flare: mirror from z_hi to z_hi + flare_z
    for u in np.linspace(1.0, 0.0, n_arc):
        z = z_hi + flare_z * (1.0 - u)
        r = r_out + flare_r * (1.0 - math.sqrt(max(0.0, 1.0 - u * u)))
        pts.append((r, z))
    pts.append((r_in, z_hi + flare_z))

    # Build manifold3d revolve
    poly = np.array(pts, dtype=float)
    cs = manifold3d.CrossSection([poly])
    m = manifold3d.Manifold.revolve(cs, circular_segments=n_seg)
    return m


def trimesh_to_manifold(tm):
    mesh = manifold3d.Mesh(
        vert_properties=np.asarray(tm.vertices, dtype=np.float32),
        tri_verts=np.asarray(tm.faces, dtype=np.uint32),
    )
    return manifold3d.Manifold(mesh)


def manifold_to_trimesh(mf):
    m = mf.to_mesh()
    verts = np.asarray(m.vert_properties[:, :3], dtype=float)
    faces = np.asarray(m.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=True)


def build_filleted_lattice(R_mm, include_ring12_arm_collar=False):
    """Add symmetric concave-flared fillet collars around the hub rings of M6 lattice.
    Snaps Z_LO / Z_HI cut-face vertices back to exact float64 so body_bond.py tol=1e-6 clamping matches.
    """
    solid_base, crop_base = BS.lattice()
    mf = trimesh_to_manifold(solid_base)
    collars = []
    for idx, (zlo, zhi) in enumerate(BS.RING_Z):
        if idx in (0, 3):
            collars.append(revolved_collar(r_in=6.5, r_out=8.48, z_lo=zlo, z_hi=zhi, flare_z=R_mm, flare_r=R_mm))
        else:
            collars.append(revolved_collar(r_in=6.5, r_out=8.48, z_lo=zlo, z_hi=zhi, flare_z=R_mm, flare_r=R_mm))
            if include_ring12_arm_collar:
                # Reinforce the ring_1 / ring_2 arm-root junction (r = 11.4..12.4 mm, strictly < 13.0 mm)
                collars.append(revolved_collar(r_in=8.3, r_out=11.4, z_lo=zlo, z_hi=zhi, flare_z=R_mm, flare_r=R_mm))
    mf_out = manifold3d.Manifold.batch_boolean([mf] + collars, manifold3d.OpType.Add)
    tm_out = manifold_to_trimesh(mf_out)

    # Restore exact float64 Z_LO / Z_HI cut-face coordinates (manifold3d uses float32)
    v = np.asarray(tm_out.vertices, float).copy()
    v[np.abs(v[:, 2] - BS.Z_LO) < 1e-4, 2] = BS.Z_LO
    v[np.abs(v[:, 2] - BS.Z_HI) < 1e-4, 2] = BS.Z_HI
    tm_out = trimesh.Trimesh(vertices=v, faces=tm_out.faces, process=False)

    # Geometry & clearance checks
    r = np.hypot(v[:, 0], v[:, 1])
    z = v[:, 2]
    bore_min_r = {}
    for idx, (zlo, zhi) in enumerate(BS.RING_Z):
        msk = (z >= zlo) & (z <= zhi) & (r < 6.0)
        bore_min_r[f"ring_{idx}"] = float(r[msk].min())

    info = dict(
        R_mm=R_mm,
        include_ring12_arm_collar=include_ring12_arm_collar,
        is_watertight=bool(tm_out.is_watertight),
        body_count=int(tm_out.body_count),
        clamped_surface_verts=int((np.abs(z - BS.Z_LO) < 1e-6).sum()),
        d1_surface_verts=int((np.abs(z - BS.Z_HI) < 1e-6).sum()),
        base_volume_mm3=float(solid_base.volume),
        filleted_volume_mm3=float(tm_out.volume),
        added_volume_mm3=float(tm_out.volume - solid_base.volume),
        added_mass_g=float((tm_out.volume - solid_base.volume) * PA12_DENSITY_G_PER_MM3),
        bore_min_radius_mm=bore_min_r,
        bore_preserved_8p40mm=all(abs(val - 4.20) < 0.01 for val in bore_min_r.values()),
        faces=len(tm_out.faces),
    )
    assert info["is_watertight"] and info["body_count"] == 1 and info["bore_preserved_8p40mm"], info
    assert info["clamped_surface_verts"] > 50 and info["d1_surface_verts"] > 50, info
    return tm_out, info


def evaluate_candidate(name, solid_mesh, geom_info, S, Cb, rhs15, K_cad, mesh_levels):
    """Run FE on the filleted CAD candidate using the CAD sleeve backbone (L = 66 mm)."""
    orig_lattice = BS.lattice
    BS.lattice = lambda: (solid_mesh, geom_info)
    MB._install_safe_tet_mesh()
    rec = dict(name=name, geometry=geom_info, levels=[])
    try:
        for label, q, mv in mesh_levels:
            tl = time.monotonic()
            B = BB.Body(q, mv, 0.08)
            Kt_bare = B.system(500.0, 0.06)
            Kt_cad = BF.add_k(B, Kt_bare, K_cad)
            U15, resid = B.solve(Kt_cad, rhs15)

            # Equivalent EI (bare & with CAD sleeve backbone) on q3
            ei_info = {}
            if label == "q3_a040":
                for ename, Km in (("bare", Kt_bare), ("cad_sleeve_L66", Kt_cad)):
                    Uu, _ = MB.solve_load_controlled(B, Km, [(np.eye(3)[i], np.zeros(12)) for i in range(2)])
                    C = Uu[B.c1 + 3: B.c1 + 5, :]
                    ei_info[ename] = [float(MB.BB_L_CROP / C[0, 0]), float(MB.BB_L_CROP / C[1, 1])]

            steps_out = {}
            for s in (1709, 1869, 1884):
                st_res = SHS.analyze_step(B, Kt_bare, K_cad, U15 @ Cb[s])
                steps_out[str(s)] = st_res
                g = st_res["global_max"]
                r0 = st_res["ring0_hotspot"]
                r1 = st_res["ring1_hotspot"]
                print(
                    f"  [{name} | {label}] step {s}: global={g['peak_abs_principal_strain']*100:.3f}% @ z={g['peak_location_mm'][2]:+.2f} | "
                    f"ring0={r0['peak_abs_principal_strain']*100:.3f}% (g0.5={r0['finite_gauge_at_peak']['r_0.5mm']['tensor_avg_principal_strain']*100:.3f}%) | "
                    f"ring1={r1['peak_abs_principal_strain']*100:.3f}% (g0.5={r1['finite_gauge_at_peak']['r_0.5mm']['tensor_avg_principal_strain']*100:.3f}%)",
                    flush=True,
                )
            rec["levels"].append(dict(
                label=label, mesh=B.mesh, solve_residual=resid, equivalent_EI_over_85p8mm_Nmm2=ei_info,
                steps=steps_out, elapsed_s=time.monotonic() - tl,
            ))
            del B, Kt_bare, Kt_cad, U15
    finally:
        BS.lattice = orig_lattice
    return rec


def main():
    t0 = time.monotonic()
    started = stamp()
    OUT.mkdir(parents=True, exist_ok=True)

    S = np.load(EV25 / "results/rod_steps.npz")
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    rhs15 = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]
    K_cad, _ = BF.sleeve_backbone_stiffness_d1()

    candidates = []
    for R_mm, inc_arm, name, run_q25 in [
        (0.8, False, "hub_fillet_R0p8", False),
        (1.0, True, "hub_plus_arm_R1p0", True),
    ]:
        print(f"\n=== Building & checking CAD candidate '{name}' (R = {R_mm} mm, arm_collar={inc_arm}) ===", flush=True)
        mesh_f, ginfo = build_filleted_lattice(R_mm, include_ring12_arm_collar=inc_arm)
        print(f"  watertight={ginfo['is_watertight']}, bodies={ginfo['body_count']}, "
              f"clamped_v={ginfo['clamped_surface_verts']}, d1_v={ginfo['d1_surface_verts']}, "
              f"bore_ok={ginfo['bore_preserved_8p40mm']}, +vol={ginfo['added_volume_mm3']:.1f} mm^3 (+{ginfo['added_mass_g']:.3f} g)", flush=True)
        mlevels = [("q3_a040", 3.0, 0.40)] + ([("q2p5_a025", 2.5, 0.25)] if run_q25 else [])
        res = evaluate_candidate(name, mesh_f, ginfo, S, Cb, rhs15, K_cad, mlevels)
        candidates.append(res)

    finished = stamp()
    doc = dict(
        task="Stage 2: Hub/arm fillet CAD study with CAD sleeve NiTi backbone (L=66 mm)",
        started_et=started["et"],
        started_utc=started["utc"],
        completed_at_et=finished["et"],
        completed_at_utc=finished["utc"],
        elapsed_s=time.monotonic() - t0,
        candidates=candidates,
    )
    (OUT / "fillet_study.json").write_text(json.dumps(doc, indent=1, default=float))
    print(f"\nDone Stage 2 in {time.monotonic() - t0:.1f}s! Saved {OUT / 'fillet_study.json'}", flush=True)


if __name__ == "__main__":
    main()
