"""Peak strain of the whole-body solid field (body_bond, q5 mesh, G = 500 MPa, crowned, step 1,709,
"local" moment scaling + station wrenches) - a validity check of the linear small-strain model.
Writes results/strain_check.json."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import body_bond as BB  # noqa: E402
F = BB.F


def element_strain(X, conn, u):
    g, _ = F.bary_grad(X[conn[:, :4]])
    _, dN = F.shape(np.full((1, 4), 0.25))
    G = np.einsum("nk,ekx->enx", dN[0], g)  # (ne,10,3)
    H = np.einsum("eai,eaj->eij", u[conn], G)  # displacement gradient
    return 0.5 * (H + H.transpose(0, 2, 1)), H


def main():
    rod, zs, _ = BB.CB.load_motion()
    B = BB.Body(5.0, 0.4, 0.08)
    W = {st: BB.CB.station_wrenches("M6", st) for st in BB.STATIONS}
    s = 1709
    rot = BB.rod_rotations(rod, rod.kinematic_metrics(zs[s])[1])
    U, _ = B.solve(B.system(500.0, 0.06), [(rot["end_rotvec"], np.zeros(12)), (np.zeros(3), np.r_[W[-12][s], W[12][s]])])
    out = {}
    for name, Ul in (("end_moment_only", U[:, 0]), ("wrench_only", U[:, 1]), ("end_moment_plus_wrench", U[:, 0] + U[:, 1])):
        u = (B.T @ Ul[:B.n]).reshape(-1, 3)
        eps, H = element_strain(B.X, B.conn, u)
        ev = np.linalg.eigvalsh(eps)
        peak = np.abs(ev).max(1)
        rotmag = np.linalg.norm(0.5 * (H - H.transpose(0, 2, 1)), axis=(1, 2)) / np.sqrt(2)
        c = B.X[B.conn[:, :4]].mean(1)
        r = np.hypot(c[:, 0], c[:, 1])
        i = int(np.argmax(peak))
        out[name] = dict(peak_abs_principal_strain=float(peak.max()), p99_9=float(np.percentile(peak, 99.9)),
                         p99=float(np.percentile(peak, 99)), median=float(np.median(peak)),
                         peak_location_mm=c[i].tolist(), peak_r_mm=float(r[i]),
                         volume_fraction_above_2pct=float((peak > 0.02).mean()),
                         max_linearised_rotation_rad=float(rotmag.max()),
                         peak_in_land_bands=float(peak[(np.abs(np.abs(c[:, 2]) - 12) < 0.6) & (r > 15) & (r < 24)].max()))
        print(name, {k: (round(v, 5) if isinstance(v, float) else v) for k, v in out[name].items()}, flush=True)
    (HERE / "results" / "strain_check.json").write_text(json.dumps(dict(scope=__doc__, step=s, mesh=B.mesh, cases=out), indent=1, default=float))


if __name__ == "__main__":
    main()
