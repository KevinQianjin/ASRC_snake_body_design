"""Mission envelope of the peak body strain of the linear bonded solid model (validity limit of the
24 Nov run, extended from step 1,709 to all 3,405 mission states by superposition).

Same case as ``evening_20261124/strain_check.py`` (q5 mesh, G = 500 MPa, crowned 0.06 mm land,
end rotation + both station wrenches, no "local" scaling). The element-centroid small-strain tensor
is linear in the 15 unit solutions; per step the exact peak |principal strain| is found by
evaluating eigenvalues only on elements whose Frobenius norm can still exceed the running maximum
(|lambda|max <= ||eps||_F). Linear small strain; the 24 Nov total-Lagrangian check put the
geometric-nonlinearity effect on the peak at ~1% for step 1,709. Writes results/strain_envelope.json.
"""
import json, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mission_envelope as ME  # noqa: E402
BB = ME.BB
sys.path.insert(0, str(HERE.parent / "evening_20261124"))
from strain_check import element_strain  # noqa: E402


def main():
    t0 = time.monotonic()
    S = np.load(HERE / "results/rod_steps.npz"); n = len(S["end_rotvec"]); phase = ME.phase_of(n)
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]  # (n,15)
    B = BB.Body(5.0, 0.4, 0.08)
    rhs = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]
    U, resid = B.solve(B.system(500.0, 0.06), rhs)
    E = np.stack([element_strain(B.X, B.conn, (B.T @ U[:B.n, j]).reshape(-1, 3))[0] for j in range(15)], -1)  # (ne,3,3,15)
    iu = [(0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2)]
    E6 = np.stack([E[:, i, j] for i, j in iu], 1)  # (ne,6,15)
    wF = np.array([1, 1, 1, 2, 2, 2.0])
    c = B.X[B.conn[:, :4]].mean(1); r = np.hypot(c[:, 0], c[:, 1])
    band = (np.abs(np.abs(c[:, 2]) - 12) < 0.6) & (r > 15) & (r < 24)
    peak = np.empty(n); where = np.empty(n, int); pband = np.empty(n); evals = 0
    for i0 in range(0, n, 50):
        Cc = Cb[i0:i0 + 50]
        e6 = np.einsum("eck,sk->sec", E6, Cc, optimize=True)  # (s,ne,6)
        fro = np.sqrt((e6 ** 2 * wF).sum(-1))
        for k in range(len(Cc)):
            def princ(idx):
                m = np.zeros((len(idx), 3, 3)); v = e6[k, idx]
                for q, (a, b) in enumerate(iu): m[:, a, b] = v[:, q]; m[:, b, a] = v[:, q]
                return np.abs(np.linalg.eigvalsh(m)).max(1)
            top = np.argpartition(fro[k], -64)[-64:]
            best = princ(top).max()
            cand = np.flatnonzero(fro[k] >= best)
            p = princ(cand); j = int(np.argmax(p)); evals += len(cand)
            peak[i0 + k] = p[j]; where[i0 + k] = cand[j]
            bi = np.flatnonzero(band)
            pband[i0 + k] = princ(bi[fro[k][bi] >= princ(bi[np.argsort(fro[k][bi])[-16:]]).max()]).max()

    s = int(peak.argmax())
    doc = dict(scope=__doc__, mesh=B.mesh, solve_residual=resid, n_steps=n,
               at_1709=dict(peak=float(peak[1709]), location_mm=c[where[1709]].tolist(), land_band_peak=float(pband[1709])),
               mission_max=dict(peak=float(peak[s]), step=s, phase=ME.PHASES[phase[s]], location_mm=c[where[s]].tolist(),
                                r_mm=float(r[where[s]]), end_rotation_deg=float(np.degrees(np.linalg.norm(S["end_rotvec"][s])))),
               land_band_mission_max=dict(peak=float(pband.max()), step=int(pband.argmax())),
               steps_above_3pct=int((peak > 0.03).sum()), steps_above_2pct=int((peak > 0.02).sum()),
               by_phase={p: dict(max=float(peak[phase == i].max()), step=int(np.flatnonzero(phase == i)[peak[phase == i].argmax()]))
                         for i, p in enumerate(ME.PHASES)},
               eigen_evaluations=evals, elapsed_s=time.monotonic() - t0)
    np.savez_compressed(HERE / "results/strain_envelope.npz", peak=peak, land_band_peak=pband, element=where)
    (HERE / "results/strain_envelope.json").write_text(json.dumps(doc, indent=1, default=float))
    print(json.dumps({k: v for k, v in doc.items() if k not in ("scope", "mesh")}, indent=1, default=float))


if __name__ == "__main__":
    main()
