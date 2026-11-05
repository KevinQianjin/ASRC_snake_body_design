"""Additional finite top-tendon sweep at 25/30 degree interface pitches."""
from __future__ import annotations
import json
import numpy as np
from front_solver import FrontRod, HERE, write_csv
from refine_front import finer_seed, geometry_screen, stiffness_with_extra_rope


def run():
    output = HERE/'results'
    output.mkdir(parents=True, exist_ok=True)
    rows, attempts, fine_rows, arrays = [], [], [], {}
    for n_uni in (3, 5, 7):
        for pitch in (25, 30):
            r = FrontRod(n_uni, pitch, sub=4)
            free = r.free_state()
            previous = free
            for force in (0., .5, 1., 2., 4., 6., 8., 10., 12., 16.):
                T = r.sweep_tensions(force, 0.)
                got = r.solve_force(T, previous) if previous is not None else None
                if got is None and free is not None:
                    got = r.solve_force(T, free)
                attempt = dict(configuration=r.label, pitch_deg=pitch,
                               signed_drive_n=force, common_per_rope_n=0.,
                               status='converged' if got is not None else 'not_converged')
                attempts.append(attempt)
                if got is None:
                    continue
                previous = got
                metric, points, disks, data = r.metrics(got, T)
                state_id = f'e{len(rows):03d}'
                metric.update(attempt, state_id=state_id, record_type='coarse_sweep')
                rows.append(metric)
                arrays[state_id+'_x'] = got
                arrays[state_id+'_points_m'] = points
                arrays[state_id+'_disks_m'] = disks
                arrays[state_id+'_theta_rad'] = data['theta']
                arrays[state_id+'_strain'] = data['eps']
                arrays[state_id+'_tensions_n'] = T
            eligible = [z for z in rows if z['configuration'] == r.label and z['pitch_deg'] == pitch
                        and z['stable_in_plane'] and not z['axial_strain_exceeds_5_percent']]
            if not eligible:
                fine_rows.append(dict(configuration=r.label, pitch_deg=pitch,
                                      record_type='best_refinement', refinement_converged=False,
                                      note='No coarse stable small-strain candidate was found.'))
                continue
            best = max(eligible, key=lambda z: z['tip_x_mm'])
            fine = FrontRod(n_uni, pitch, sub=8)
            T = np.array(best['tensions_n'])
            initial = finer_seed(arrays[best['state_id']+'_x'], r, fine)
            got = fine.solve_force(T, initial, maxiter=180)
            state_id = f'ef{len(fine_rows):03d}'
            result = dict(configuration=r.label, pitch_deg=pitch, state_id=state_id,
                          original_state_id=best['state_id'], record_type='best_refinement',
                          refinement_converged=got is not None,
                          control_comparison='same_tensions_not_same_winch_commands')
            if got is not None:
                metric, points, disks, data = fine.metrics(got, T)
                result.update(metric)
                result['pitch_deg'] = pitch
                result.update(geometry_screen(points, data, fine))
                old_points = arrays[best['state_id']+'_points_m']
                s4 = np.r_[0., .020+np.arange(r.m+1)*r.l]
                s8 = np.r_[0., .020+np.arange(fine.m+1)*fine.l]
                interpolated = np.c_[np.interp(s8, s4, old_points[:, 0]),
                                     np.interp(s8, s4, old_points[:, 1])]
                result.update(tip_change_mm=float(np.linalg.norm(points[-1]-old_points[-1])*1000),
                              max_centerline_change_mm=float(np.max(np.linalg.norm(points-interpolated, axis=1))*1000),
                              extra_rope_eigenvalue=stiffness_with_extra_rope(fine, got, T),
                              extra_free_rope_m=1.,
                              rope_sensitivity_scope='unchanged_pose_and_tension_tangent_stiffness_not_same_command_resolve')
                arrays[state_id+'_x'] = got
                arrays[state_id+'_points_m'] = points
                arrays[state_id+'_disks_m'] = disks
                arrays[state_id+'_theta_rad'] = data['theta']
                arrays[state_id+'_strain'] = data['eps']
                arrays[state_id+'_tensions_n'] = T
            fine_rows.append(result)
            print(f'{r.label} {pitch} deg: best {best["state_id"]} -> {state_id}, refined={got is not None}', flush=True)
    records = rows+fine_rows
    (output/'front_angle_extension.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    write_csv(output/'front_angle_extension.csv', records)
    write_csv(output/'front_angle_extension_attempts.csv', attempts)
    np.savez_compressed(output/'front_angle_extension_states.npz', **arrays)
    summary = dict(attempted=len(attempts), converged_coarse=len(rows),
                   refined_best=sum(z['refinement_converged'] for z in fine_rows),
                   finite_search_pitches_deg=[25, 30],
                   note='Finite planar angle extension; no global feasibility claim.')
    (output/'front_angle_extension_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
