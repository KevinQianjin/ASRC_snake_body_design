"""Stage 1: Refined-mesh (q5 -> q3 -> q2.5/a0.25) hub-junction strain with CAD sleeve NiTi backbone.

Executes Priority 1 of morning_20261127/HANDOFF.md (Priority 2 of evening_20261126/HANDOFF.md):
Replaces the superseded 85.8 mm cut-face backbone attachment with the CAD-consistent L = 66 mm
sleeve attachment (bore_fe.sleeve_backbone_stiffness_d1()) on q5, q3, and q2.5/a0.25 meshes.
Tracks BOTH candidate hotspots separately (ring_0 side z ~ -17.9 mm and ring_1 side z ~ -5.2 mm)
plus the global peak and 0.5 / 1.0 mm finite-gauge volume-averaged strains, and runs the full
3,405-state mission strain envelope on the finest mesh (q2.5/a0.25).
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
EV26 = HERE.parent / "evening_20261126"
MORN26 = HERE.parent / "morning_20261126"
EV25 = HERE.parent / "evening_20261125"
EV24 = HERE.parent / "evening_20261124"
for p in (EV26, MORN26, EV25, EV24):
    sys.path.insert(0, str(p))

import backbone_strain as MB  # noqa: E402
import bore_fe as BF  # noqa: E402
import mission_envelope as ME  # noqa: E402
from strain_check import element_strain  # noqa: E402

OUT = HERE / "results"


def stamp():
    now = datetime.now(timezone.utc)
    return dict(
        et=now.astimezone(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def region_strain_metrics(B, eps, peak, c, r, vol, mask, gauge_radii=(0.5, 1.0)):
    """Peak element strain, location, edge size, and finite-gauge averages within `mask`."""
    idxs = np.flatnonzero(mask)
    i = int(idxs[np.argmax(peak[idxs])])
    Xv = B.X[B.conn[i, :4]]
    edges = [np.linalg.norm(Xv[a] - Xv[b]) for a in range(4) for b in range(a + 1, 4)]
    d_to_peak = np.linalg.norm(c - c[i], axis=1)
    gauges = {}
    for rg in gauge_radii:
        m = d_to_peak <= rg
        w = vol[m]
        eps_avg = np.tensordot(w, eps[m], axes=(0, 0)) / w.sum()
        gauges[f"r_{rg:.1f}mm"] = dict(
            n_tets=int(m.sum()),
            tensor_avg_principal_strain=float(np.abs(np.linalg.eigvalsh(eps_avg)).max()),
            scalar_avg_principal_strain=float((w * peak[m]).sum() / w.sum()),
        )
    return dict(
        peak_abs_principal_strain=float(peak[i]),
        peak_location_mm=c[i].tolist(),
        peak_r_mm=float(r[i]),
        peak_tet_mean_edge_mm=float(np.mean(edges)),
        finite_gauge_at_peak=gauges,
    )


def analyze_step(B, Kt_bare, K_cad, Ul):
    u = (B.T @ Ul[:B.n]).reshape(-1, 3)
    eps, _ = element_strain(B.X, B.conn, u)
    ev = np.linalg.eigvalsh(eps)
    peak = np.abs(ev).max(1)
    c = B.X[B.conn[:, :4]].mean(1)
    r = np.hypot(c[:, 0], c[:, 1])
    Xv = B.X[B.conn[:, :4]]
    vol = np.abs(np.linalg.det(Xv[:, 1:] - Xv[:, :1])) / 6.0

    m_all = np.ones(len(peak), dtype=bool)
    m_ring0 = (c[:, 2] >= -21.5) & (c[:, 2] <= -14.5) & (r >= 6.0) & (r <= 12.0)
    m_ring1 = (c[:, 2] >= -8.5) & (c[:, 2] <= -1.5) & (r >= 6.0) & (r <= 12.0)
    m_ring2 = (c[:, 2] >= 1.5) & (c[:, 2] <= 8.5) & (r >= 6.0) & (r <= 12.0)
    m_ring3 = (c[:, 2] >= 14.5) & (c[:, 2] <= 21.5) & (r >= 6.0) & (r <= 12.0)
    m_land = (np.abs(np.abs(c[:, 2]) - 12.0) < 0.6) & (r > 15.0) & (r < 24.0)

    c1 = B.c1
    R_body = (Kt_bare @ Ul)[c1 + 3: c1 + 6]
    R_bb = (K_cad @ Ul[c1: c1 + 6])[3:6]
    R_tot = R_body + R_bb
    nt = float(np.linalg.norm(R_tot))

    return dict(
        global_max=region_strain_metrics(B, eps, peak, c, r, vol, m_all),
        ring0_hotspot=region_strain_metrics(B, eps, peak, c, r, vol, m_ring0),
        ring1_hotspot=region_strain_metrics(B, eps, peak, c, r, vol, m_ring1),
        ring2_hotspot=region_strain_metrics(B, eps, peak, c, r, vol, m_ring2),
        ring3_hotspot=region_strain_metrics(B, eps, peak, c, r, vol, m_ring3),
        land_band_peak=float(peak[m_land].max()),
        moment_split=dict(
            M_body_norm_Nmm=float(np.linalg.norm(R_body)),
            M_backbone_norm_Nmm=float(np.linalg.norm(R_bb)),
            M_total_norm_Nmm=nt,
            body_share=float(np.linalg.norm(R_body) / nt),
            backbone_share=float(np.linalg.norm(R_bb) / nt),
        ),
    )


def main():
    t0 = time.monotonic()
    started = stamp()
    OUT.mkdir(parents=True, exist_ok=True)

    S = np.load(EV25 / "results/rod_steps.npz")
    n = len(S["end_rotvec"])
    phase = ME.phase_of(n)
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    rhs15 = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]
    K_cad, _ = BF.sleeve_backbone_stiffness_d1()

    levels = [
        ("q5_a040", 5.0, 0.40),
        ("q3_a040", 3.0, 0.40),
        ("q2p5_a025", 2.5, 0.25),
    ]
    results = []
    env_finest = None

    for label, q, mv in levels:
        tl = time.monotonic()
        print(f"\n=== Mesh '{label}' (q={q}, max_vol={mv}, CAD sleeve L=66 mm) ===", flush=True)
        B = MB.build_body(q, mv, 0.08, refine_passes=0)
        Kt_bare = B.system(500.0, 0.06)
        Kt_cad = BF.add_k(B, Kt_bare, K_cad)
        U15, resid = B.solve(Kt_cad, rhs15)
        rec = dict(label=label, mesh=B.mesh, solve_residual=resid, steps={})
        for s in (1709, 1866, 1869, 1884):
            Ul = U15 @ Cb[s]
            st_res = analyze_step(B, Kt_bare, K_cad, Ul)
            rec["steps"][str(s)] = st_res
            g = st_res["global_max"]
            r0 = st_res["ring0_hotspot"]
            r1 = st_res["ring1_hotspot"]
            print(
                f"  step {s}: global={g['peak_abs_principal_strain']*100:.3f}% @ z={g['peak_location_mm'][2]:+.2f} | "
                f"ring0={r0['peak_abs_principal_strain']*100:.3f}% (g0.5={r0['finite_gauge_at_peak']['r_0.5mm']['tensor_avg_principal_strain']*100:.3f}%) | "
                f"ring1={r1['peak_abs_principal_strain']*100:.3f}% (g0.5={r1['finite_gauge_at_peak']['r_0.5mm']['tensor_avg_principal_strain']*100:.3f}%) | "
                f"bb_share={st_res['moment_split']['backbone_share']*100:.1f}%",
                flush=True,
            )
        if label == "q2p5_a025":
            print("  Running full 3,405-state strain envelope on finest mesh q2p5_a025...", flush=True)
            env_finest, pk, pb, wh = MB.run_full_strain_envelope(B, U15, S, phase)
            np.savez_compressed(OUT / "strain_envelope_sleeve_q2p5.npz", peak=pk, land_band_peak=pb, element=wh)
            print(
                f"  Finest envelope: max={env_finest['mission_max']['peak']*100:.3f}% @ step {env_finest['mission_max']['step']} "
                f"(z={env_finest['mission_max']['location_mm'][2]:+.2f} mm), >3%: {env_finest['steps_above_3pct']}, >2%: {env_finest['steps_above_2pct']}",
                flush=True,
            )
        rec["elapsed_s"] = time.monotonic() - tl
        results.append(rec)
        del B, Kt_bare, Kt_cad, U15

    # Convergence check q3 -> q2.5 at both hotspots (step 1869 and 1709)
    conv = {}
    for s in ("1709", "1869"):
        conv[s] = {}
        for hkey in ("global_max", "ring0_hotspot", "ring1_hotspot"):
            v3 = results[1]["steps"][s][hkey]["peak_abs_principal_strain"]
            v25 = results[2]["steps"][s][hkey]["peak_abs_principal_strain"]
            rel = (v25 - v3) / v3
            conv[s][hkey] = dict(q3=v3, q2p5=v25, rel_change=rel, passes_5pct=bool(abs(rel) < 0.05))
            print(f"Convergence step {s} {hkey:14s}: q3={v3*100:.3f}% -> q2.5={v25*100:.3f}% ({rel*100:+.2f}%)", flush=True)

    finished = stamp()
    doc = dict(
        task="Stage 1: Refined-mesh hub-junction strain with CAD sleeve NiTi backbone (L=66 mm)",
        started_et=started["et"],
        started_utc=started["utc"],
        completed_at_et=finished["et"],
        completed_at_utc=finished["utc"],
        elapsed_s=time.monotonic() - t0,
        parameters=dict(G_MPa=500.0, crown_mm=0.06, sleeve_L_free_mm=66.0, bb_E_MPa=40000.0, bb_d_mm=1.8),
        levels=results,
        convergence_q3_to_q2p5=conv,
        finest_mesh_envelope=env_finest,
    )
    (OUT / "sleeve_hub_strain.json").write_text(json.dumps(doc, indent=1, default=float))
    print(f"\nDone Stage 1 in {time.monotonic() - t0:.1f}s! Saved {OUT / 'sleeve_hub_strain.json'}", flush=True)


if __name__ == "__main__":
    main()
