"""Re-check U4+M2 backbone straightening and tank entry with 1 N pretension on every rope.

Finding (2026-11-09): the straightened states from backbone_planar.py, which
tension only the up ropes, are laterally unstable in 3D under the fixed-winch
check, although the planar (in-plane) check passes. A 1 N common tension on all
four ropes of every set stabilises them. This script re-optimises the planar
straightening with common=1 N (anchors [4,5,6]), re-checks 3D fixed-winch
stability with the spatial model (8 cells), and repeats the entry screen.
"""
import json
import numpy as np
from backbone import planar_rod, spatial_rod, HERE
from run_sweep import score, COARSE_BOUND
from refine_front import finer_seed
from postprocess import path_check, OLD
from lightweight_path_check import Obstacles
from spatial_model import refine_seed

OUT = HERE / 'results'
ANCH = [4, 5, 6]


def main(pre=1.):
    cad = json.loads((OLD / 'results/cad_sections.json').read_text())
    obstacles = Obstacles(cad['sections']); profiles = np.load(OLD / 'results/cavity_profiles.npz')
    prior = json.loads((OUT / 'planar_U4_M2_rows.json').read_text())
    out = []
    for v in ['niti18_E40', 'niti18_E75']:
        for p in [15, 20, 25]:
            r = planar_rod(4, 2, ANCH, p, 4, v, common=pre)
            seed_row = next(q for q in prior if q.get('variant') == v and round(q['pitch_deg']) == p
                            and q.get('architecture') == 'three_distal' and q.get('strain_mode') == 'low_strain')
            D0 = np.array(seed_row['top_extra_tensions_n'])
            x0 = r.solve_ramped(D0, r.straight_seed())
            best = None
            for x, D in [(x0, D0), (r.free(), np.zeros(3))]:
                if x is None: continue
                xx, DD, info = r.optimize(x, D, COARSE_BOUND)
                if r.residual(r.evaluate(xx, r.control_matrix(DD))[1]) < 2e-7:
                    sc = score(r.metrics(xx, DD)[0])
                    if best is None or sc < best[0]: best = (sc, xx, DD)
            _, x, D = best
            f = planar_rod(4, 2, ANCH, p, 8, v, common=pre)
            xf = f.solve_ramped(D, finer_seed(x, r, f))
            row, pts, _ = f.metrics(xf, D, geometry=True)
            # 3D fixed-winch stability of the same state, 8 cells, rope tensions incl. pretension.
            s8 = spatial_rod(4, 2, ANCH, p, 8, v)
            C = f.control_matrix(D)
            z = s8.solve(C, s8.lift_planar(xf))
            m3, _, _ = s8.metrics(z, C, stability=True) if z is not None else ({'stable_fixed_winch': None, 'yaw_deg': None, 'minimum_fixed_winch_eigenvalue': None}, 0, 0)
            # Entry screen with this shape.
            row.update(state_id=f'pre{pre:g}_{v}_p{p}', architecture='three_distal', strain_mode='low_strain')
            e, _, _ = path_check(row, pts, obstacles, profiles)
            rec = dict(variant=v, pitch_deg=p, pretension_n=pre, anchors=ANCH, top_extra_tensions_n=D.tolist(),
                       offset_mm=row['maximum_axis_deviation_mm'], tangent_deg=row['maximum_tangent_error_deg'],
                       projection=row['axial_projection_fraction'], max_strain=row['max_abs_axial_strain'],
                       planar_all_straight_pass=row['all_straight_diagnostics_pass'],
                       stable_3d_fixed_winch=m3['stable_fixed_winch'], eig_3d=m3['minimum_fixed_winch_eigenvalue'], yaw_3d_deg=m3['yaw_deg'],
                       entry_min_gap_mm=e['minimum_sampled_envelope_clearance_mm'], entry_pass=e['front_only_continuous_translation_screen_pass'])
            out.append(rec)
            print(f"{v} {p}: T {np.round(D,1)} +{pre:g} N all ropes | offset {rec['offset_mm']:.2f} tan {rec['tangent_deg']:.2f} "
                  f"strain {100*rec['max_strain']:.2f}% straight {rec['planar_all_straight_pass']} | 3D stable {rec['stable_3d_fixed_winch']} "
                  f"(yaw {rec['yaw_3d_deg']}) | entry gap {rec['entry_min_gap_mm']:.1f} pass {rec['entry_pass']}", flush=True)
    (OUT / f'pretension{pre:g}_recheck.json').write_text(json.dumps(out, indent=1, default=float))


if __name__ == '__main__':
    main()
