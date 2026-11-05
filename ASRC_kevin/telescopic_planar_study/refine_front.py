"""Same-tension front mesh checks, local stiffness sensitivity and geometry screens.

All outputs are separate from the original front sweep. An added 1 m free tendon
length changes the fixed-winch tangent stiffness only, at unchanged pose/tension;
it is not a re-solve at identical winch commands.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np
from front_solver import FrontRod, HERE, write_csv


def finer_seed(x, coarse, fine):
    seed = np.zeros(fine.ndof)
    theta = np.r_[coarse.root_pitch, x[::2]]
    seed[::2] = np.interp(np.linspace(0, 1, fine.m+1)[1:],
                           np.linspace(0, 1, coarse.m+1), theta)
    # Each coarse constant-strain cell is split evenly.
    seed[1::2] = np.repeat(x[1::2], fine.sub//coarse.sub)
    return seed


def segment_distance(a, b, c, d):
    """Exact closest distance between 2D segments, including intersections."""
    u, v, w = b-a, d-c, a-c
    cross = lambda x, y: x[0]*y[1]-x[1]*y[0]
    den = cross(u, v)
    if abs(den) > 1e-20:
        t, s = cross(c-a, v)/den, cross(c-a, u)/den
        if -1e-12 <= t <= 1+1e-12 and -1e-12 <= s <= 1+1e-12:
            return 0.
    def point_segment(p, q, r):
        z = r-q
        norm = z@z
        t = 0. if norm < 1e-30 else np.clip((p-q)@z/norm, 0., 1.)
        return float(np.linalg.norm(p-q-t*z))
    return min(point_segment(a, c, d), point_segment(b, c, d),
               point_segment(c, a, b), point_segment(d, a, b))


def geometry_screen(points, data, rod):
    nominal_s = np.r_[0., rod.interface_length+np.arange(rod.m+1)*rod.l]
    minimum = float('inf')
    minimum_pair = None
    simple = True
    # Non-adjacent centerline chord intersections, and conservative capsules
    # for pairs separated by >=64 mm in original material arc coordinate.
    for i in range(len(points)-1):
        for j in range(i+2, len(points)-1):
            distance = segment_distance(points[i], points[i+1], points[j], points[j+1])
            if distance < 1e-10:
                simple = False
            if nominal_s[j]-nominal_s[i+1] >= 2*rod.diameter-1e-12:
                if distance < minimum:
                    minimum, minimum_pair = distance, [i, j]
    kappa = abs(np.diff(data['theta']))/(rod.l*(1+data['eps']))
    radius_kappa = .5*rod.diameter*kappa
    return dict(centerline_is_simple=simple,
                centerline_check="analytic_nonadjacent_polyline_segment_intersection",
                minimum_nonlocal_centerline_distance_mm=None if not np.isfinite(minimum) else minimum*1000,
                minimum_nonlocal_capsule_clearance_mm=None if not np.isfinite(minimum) else (minimum-rod.diameter)*1000,
                closest_nonlocal_segment_pair=minimum_pair,
                nonlocal_reference_arclength_separation_mm=64.,
                nonlocal_capsule_overlap=bool(minimum < rod.diameter-1e-10),
                maximum_body_radius_times_curvature=float(radius_kappa.max()),
                local_radius_curvature_exceeded=bool(radius_kappa.max() >= 1.),
                geometry_screen_scope="polyline_and_32mm_capsules_not_detailed_module_contact")


def stiffness_with_extra_rope(rod, x, tensions, extra=1.):
    _, g, H, data = rod.evaluate(x, tensions, detail=True)
    n = rod.ndof
    matrix = np.diag(H[0])
    for k in range(1, rod.bandwidth+1):
        i = np.arange(n-k)
        matrix[i+k, i] = H[k, :n-k]
        matrix[i, i+k] = H[k, :n-k]
    active = np.asarray(tensions) > 1e-7
    rest = data['rope_lengths']/(1+np.asarray(tensions)/rod.rope_ea)+extra
    G = data['rope_jac'][active]
    if len(G):
        matrix += G.T@((rod.rope_ea/rest[active])[:, None]*G)
    scale = 1/np.sqrt(np.maximum(abs(np.diag(matrix)), 1e-10))
    eigen = float(np.linalg.eigvalsh(matrix*scale[:, None]*scale[None, :])[0])
    return eigen


def run(output=None):
    output = Path(output) if output else HERE/'results'
    old = json.loads((output/'front_equilibria.json').read_text(encoding='utf-8'))
    saved = np.load(output/'front_states.npz')
    rows, arrays = [], {}
    for n_uni in (3, 5, 7):
        label = f'U{n_uni}-M{10-n_uni}'
        for pitch in (10, 15, 20):
            group = [z for z in old if z['configuration'] == label and z['pitch_deg'] == pitch]
            eligible = [z for z in group if z['stable_in_plane'] and not z['axial_strain_exceeds_5_percent']]
            best = max(eligible, key=lambda z: z['tip_x_mm'])
            coarse = FrontRod(n_uni, pitch, sub=4)
            fine = FrontRod(n_uni, pitch, sub=8)
            reference20 = min([z for z in group if z['common_per_rope_n'] == 0 and z['signed_drive_n'] >= 0],
                              key=lambda z: abs(z['signed_drive_n']-20))
            T20 = coarse.sweep_tensions(20., 0.)
            state20 = None
            # Retry both neighboring branches, and use a fine force continuation.
            candidates = sorted([z for z in group if z['common_per_rope_n'] == 0 and z['signed_drive_n'] >= 0],
                                key=lambda z: abs(z['signed_drive_n']-20))[:5]
            for candidate in candidates:
                seed20 = saved[candidate['state_id']+'_x']
                state20 = coarse.solve_force(T20, seed20)
                if state20 is None:
                    seed = seed20
                    for force in np.linspace(candidate['signed_drive_n'], 20.,
                                             max(2, int(abs(candidate['signed_drive_n']-20)*2)+1))[1:]:
                        seed = coarse.solve_force(coarse.sweep_tensions(float(force), 0.), seed)
                        if seed is None:
                            break
                    state20 = seed
                if state20 is not None:
                    break
            requests = [('best_forward', best['state_id'], saved[best['state_id']+'_x'], np.array(best['tensions_n'])),
                        ('top20_diagnostic', f'new_top20_{label}_p{pitch}', state20, T20)]
            for kind, original_id, x4, T in requests:
                refined_id = f'r{len(rows):03d}'
                row = dict(refined_state_id=refined_id, selection=kind, original_state_id=original_id,
                           configuration=label, pitch_deg=pitch, tensions_n=T.tolist(),
                           control_comparison='same_tensions_not_same_winch_commands',
                           coarse_cells_per_module=4, fine_cells_per_module=8,
                           extra_free_rope_m=1.,
                           rope_sensitivity_scope='unchanged_pose_and_tension_tangent_stiffness_not_same_command_resolve')
                if x4 is None:
                    row.update(coarse_converged=False, refinement_converged=False,
                               fine_solve_attempted=True,
                               refinement_comparison_available=False)
                    got = None
                    for candidate in candidates:
                        initial = finer_seed(saved[candidate['state_id']+'_x'], coarse, fine)
                        got = fine.solve_force(T, initial, maxiter=180)
                        if got is not None:
                            break
                    row['fine_direct_solve_converged'] = got is not None
                    if got is not None:
                        metric, points, disks, data = fine.metrics(got, T)
                        row.update(fine_tip_x_mm=metric['tip_x_mm'], fine_tip_y_mm=metric['tip_y_mm'],
                                   fine_max_abs_axial_strain=float(np.max(abs(got[1::2]))),
                                   fine_axial_strain_exceeds_5_percent=metric['axial_strain_exceeds_5_percent'],
                                   fine_equilibrium_residual=metric['equilibrium_residual'],
                                   fine_fixed_length_eigenvalue=metric['minimum_scaled_fixed_length_eigenvalue'],
                                   fine_stable_in_plane=metric['stable_in_plane'],
                                   fine_extra_rope_eigenvalue=stiffness_with_extra_rope(fine, got, T))
                        row['fine_stable_with_extra_rope'] = row['fine_extra_rope_eigenvalue'] >= -1e-7
                        row.update(geometry_screen(points, data, fine))
                        arrays[refined_id+'_x'] = got
                        arrays[refined_id+'_points_m'] = points
                        arrays[refined_id+'_disks_m'] = disks
                        arrays[refined_id+'_theta_rad'] = data['theta']
                        arrays[refined_id+'_strain'] = data['eps']
                        arrays[refined_id+'_tensions_n'] = T
                    rows.append(row)
                    continue
                m4, points4, disks4, data4 = coarse.metrics(x4, T)
                row.update(coarse_converged=True,
                           coarse_tip_x_mm=m4['tip_x_mm'], coarse_tip_y_mm=m4['tip_y_mm'],
                           coarse_max_abs_axial_strain=float(np.max(abs(x4[1::2]))),
                           coarse_fixed_length_eigenvalue=m4['minimum_scaled_fixed_length_eigenvalue'],
                           coarse_extra_rope_eigenvalue=stiffness_with_extra_rope(coarse, x4, T))
                arrays[refined_id+'_coarse_x'] = x4
                arrays[refined_id+'_coarse_points_m'] = points4
                got = fine.solve_force(T, finer_seed(x4, coarse, fine), maxiter=180)
                row['fine_solve_attempted'] = True
                row['refinement_comparison_available'] = got is not None
                row['refinement_converged'] = got is not None
                if got is not None:
                    metric, points, disks, data = fine.metrics(got, T)
                    # Compare geometry at the fine reference-material coordinates.
                    s4 = np.r_[0., .020+np.arange(coarse.m+1)*coarse.l]
                    s8 = np.r_[0., .020+np.arange(fine.m+1)*fine.l]
                    interpolated = np.c_[np.interp(s8, s4, points4[:, 0]), np.interp(s8, s4, points4[:, 1])]
                    row.update(fine_tip_x_mm=metric['tip_x_mm'], fine_tip_y_mm=metric['tip_y_mm'],
                               tip_change_mm=float(np.linalg.norm(points[-1]-points4[-1])*1000),
                               max_centerline_change_mm=float(np.max(np.linalg.norm(points-interpolated, axis=1))*1000),
                               fine_max_abs_axial_strain=float(np.max(abs(got[1::2]))),
                               fine_axial_strain_exceeds_5_percent=metric['axial_strain_exceeds_5_percent'],
                               fine_equilibrium_residual=metric['equilibrium_residual'],
                               fine_fixed_length_eigenvalue=metric['minimum_scaled_fixed_length_eigenvalue'],
                               fine_stable_in_plane=metric['stable_in_plane'],
                               fine_extra_rope_eigenvalue=stiffness_with_extra_rope(fine, got, T))
                    row['fine_stable_with_extra_rope'] = row['fine_extra_rope_eigenvalue'] >= -1e-7
                    row.update(geometry_screen(points, data, fine))
                    arrays[refined_id+'_x'] = got
                    arrays[refined_id+'_points_m'] = points
                    arrays[refined_id+'_disks_m'] = disks
                    arrays[refined_id+'_theta_rad'] = data['theta']
                    arrays[refined_id+'_strain'] = data['eps']
                    arrays[refined_id+'_tensions_n'] = T
                rows.append(row)
            print(f'{label} pitch {pitch}: refinements saved', flush=True)
    write_csv(output/'front_refinements.csv', rows)
    (output/'front_refinements.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    np.savez_compressed(output/'front_refined_states.npz', **arrays)
    summary = dict(requested_states=len(rows), converged_refinements=sum(z['refinement_converged'] for z in rows),
                   converged_fine_direct_diagnostics=sum(z.get('fine_direct_solve_converged', False) for z in rows),
                   total_fine_equilibria=sum(z['refinement_converged'] or z.get('fine_direct_solve_converged', False) for z in rows),
                   max_tip_change_mm=max((z.get('tip_change_mm', 0) for z in rows), default=None),
                   max_centerline_change_mm=max((z.get('max_centerline_change_mm', 0) for z in rows), default=None),
                   comparison='same_tension_mesh_refinement',
                   geometry='analytic_polyline_and_nonlocal_capsules_not_detailed_module_contact',
                   rope_stiffness='extra_1m_at_unchanged_pose_and_tensions_not_same_winch_command_resolve')
    (output/'front_refinement_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
