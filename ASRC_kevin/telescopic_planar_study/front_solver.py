"""Finite planar diagnostic study of a U/M flexible front on a pitched interface.

The existing exact-consistent rod kernel is loaded read-only, changing only its
fixed root pitch. No old source or result is modified. This is a diagnostic
equilibrium sweep, not a design certification or a global feasibility proof.
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
KERNEL_PATH = HERE.parent / "h8u12_front5to8_payload500g" / "rope_planar.py"
source = KERNEL_PATH.read_text(encoding="utf-8")
old = "theta=np.r_[0.,x[::2]];a,b=theta[:-1],theta[1:]"
new = "theta=np.r_[self.root_pitch,x[::2]];a,b=theta[:-1],theta[1:]"
if source.count(old) != 1:
    raise RuntimeError("The original rod kernel changed; root-pitch patch needs review.")
kernel_namespace = {"__file__": str(KERNEL_PATH), "__name__": "_readonly_front_kernel"}
patched_source = source.replace(old, new).replace(".read_text()", ".read_text(encoding='utf-8')")
exec(compile(patched_source, str(KERNEL_PATH), "exec"), kernel_namespace)
BaseRod = kernel_namespace["PlanarRod"]


class FrontRod(BaseRod):
    def __init__(self, n_uni=5, pitch_deg=15, sub=4, payload_kg=.5):
        self.root_pitch = np.radians(float(pitch_deg))
        self.n_uni = int(n_uni)
        self.payload_kg = float(payload_kg)
        super().__init__((0, 0, 0, 10), sub=sub)
        # Proximal U modules use their stiff Y bending plane. No metal core.
        self.module_EI = np.r_[np.full(n_uni, .061), np.full(10-n_uni, .0046)]
        self.module_EA = np.r_[np.full(n_uni, 1150.19), np.full(10-n_uni, 85.07)]
        self.EI = np.repeat(self.module_EI, sub)
        self.EA = np.repeat(self.module_EA, sub)
        module_mass = np.r_[np.full(n_uni, .0039), np.full(10-n_uni, .004)]
        module_mass += 4*self.rope_density*.048
        self.mass = np.repeat(module_mass/sub, sub)
        self.weight_after = np.cumsum(self.mass[::-1])[::-1]-self.mass+self.payload_kg
        self.interface_length = .020

    @property
    def label(self):
        return f"U{self.n_uni}-M{10-self.n_uni}"

    def straight_seed(self):
        x = np.zeros(self.ndof)
        x[::2] = self.root_pitch
        return x

    @staticmethod
    def sweep_tensions(drive, common=0):
        # Common is the per-rope baseline, applied to all four tendons.
        return np.array([common+max(drive, 0), common,
                         common+max(-drive, 0), common], dtype=float)

    def solve_force(self, tensions, seed, gravity=9.81, maxiter=110):
        x = np.array(seed, copy=True)
        for iteration in range(maxiter):
            try:
                _, g, H = self.evaluate(x, tensions, gravity)
            except (ValueError, FloatingPointError):
                return None
            residual = self.residual(g)
            if residual < 2e-8:
                return x
            try:
                step = -self.solve_h(H, g)
            except (ValueError, np.linalg.LinAlgError):
                return None
            alpha = 1.
            accepted = False
            for _ in range(24):
                trial = x+alpha*step
                theta = np.r_[self.root_pitch, trial[::2]]
                if (np.max(np.abs(trial[1::2])) > .85 or
                        np.max(np.abs(np.diff(theta))) > 1.5 or
                        np.max(np.abs(theta-self.root_pitch)) > 8*np.pi):
                    alpha *= .5
                    continue
                try:
                    rr = self.residual(self.evaluate(trial, tensions, gravity)[1])
                except (ValueError, FloatingPointError):
                    alpha *= .5
                    continue
                if rr < residual*(1-1e-4*alpha) or rr < 2e-8:
                    x = trial
                    accepted = True
                    break
                alpha *= .5
            if not accepted:
                return None
        return None

    def free_state(self):
        seed = self.straight_seed()
        for gravity in np.linspace(9.81/20, 9.81, 20):
            result = self.solve_force(np.zeros(4), seed, gravity)
            if result is None:
                # A downward seed also permits a gravity-dominated branch.
                seed = self.straight_seed()
                seed[::2] = np.linspace(self.root_pitch, -np.pi/2, self.m)
                result = self.solve_force(np.zeros(4), seed, gravity)
            if result is None:
                return None
            seed = result
        return seed

    def metrics(self, x, tensions):
        energy, g, H, data = self.evaluate(x, tensions, detail=True)
        offset = self.interface_length*np.array([np.cos(self.root_pitch), np.sin(self.root_pitch)])
        world = data['points']+offset
        all_points = np.vstack((np.zeros(2), world))
        disk_points = np.vstack((np.zeros(2), world[::self.sub]))
        eps = data['eps']
        eigen = self.stability(H, data, np.asarray(tensions))
        head = world[-1]
        # Rigid 20 mm interface has zero assumed mass, explicitly unmeasured.
        # Root reaction includes flexible body, four rope proxy masses and payload.
        qangles = data['theta']
        a, b = qangles[:-1], qangles[1:]
        tq = a[:, None]*self.aa+b[:, None]*self.bb
        centroids = data['points'][:-1]+(1+eps)[:, None]*self.l*np.c_[
            np.sum(self.w*(1-self.u)*np.cos(tq), axis=1),
            np.sum(self.w*(1-self.u)*np.sin(tq), axis=1)]
        centroids += offset
        interface_moment = 9.81*(float(self.mass@centroids[:, 0])+self.payload_kg*head[0])
        return dict(
            configuration=self.label, n_uni=self.n_uni, n_medium=10-self.n_uni,
            pitch_deg=float(np.degrees(self.root_pitch)), cells_per_module=self.sub,
            payload_kg=self.payload_kg, nominal_front_length_mm=500., flexible_length_mm=480.,
            rigid_interface_length_mm=20., assumed_interface_mass_kg=0.,
            tensions_n=np.asarray(tensions).tolist(), total_tension_n=float(np.sum(tensions)),
            equilibrium_residual=self.residual(g), energy_j=float(energy),
            tip_x_mm=float(head[0]*1000), tip_y_mm=float(head[1]*1000),
            tip_pitch_deg=float(np.degrees(qangles[-1])),
            front_net_angle_deg=float(np.degrees(qangles[-1]-self.root_pitch)),
            max_axial_compression=float(max(0., -eps.min())),
            max_axial_extension=float(max(0., eps.max())),
            axial_strain_exceeds_5_percent=bool(np.max(np.abs(eps)) > .05),
            min_tangent_forward=float(np.cos(qangles).min()),
            min_relative_tangent_forward=float(np.cos(qangles-self.root_pitch).min()),
            current_flexible_length_mm=float(np.sum((1+eps)*self.l)*1000),
            minimum_scaled_fixed_length_eigenvalue=eigen,
            stable_in_plane=bool(eigen >= -1e-7),
            vertical_reaction_n=float(9.81*(self.mass.sum()+self.payload_kg)),
            gravity_moment_about_interface_nm=float(interface_moment),
            collision_screen_performed=False,
            material_strength_screen_performed=False,
            interpretation="diagnostic_equilibrium_not_admissibility_certification"
        ), all_points, disk_points, data


def derivative_check():
    r = FrontRod(5, 15, sub=2)
    rng = np.random.default_rng(123)
    x = r.straight_seed()+rng.normal(size=r.ndof)*.015
    x[1::2] *= .1
    T = np.array([7., 2., 1., 2.])
    v = rng.normal(size=r.ndof)
    v /= np.linalg.norm(v)
    h = 1e-6
    E, g, H, d = r.evaluate(x, T, detail=True)
    finite_g = (r.evaluate(x+h*v, T)[0]-r.evaluate(x-h*v, T)[0])/(2*h)
    analytic_h = H[0]*v
    for k in range(1, r.bandwidth+1):
        analytic_h[k:] += H[k, :-k]*v[:-k]
        analytic_h[:-k] += H[k, :-k]*v[k:]
    finite_h = (r.evaluate(x+h*v, T)[1]-r.evaluate(x-h*v, T)[1])/(2*h)
    gradient_error = abs(finite_g-g@v)
    hessian_error = float(np.max(abs(finite_h-analytic_h)))
    np.testing.assert_allclose(finite_g, g@v, atol=2e-7, rtol=2e-6)
    np.testing.assert_allclose(finite_h, analytic_h, atol=2e-6, rtol=2e-5)
    # Isolate payload contribution at nonzero pitch; constant rigid offset cancels.
    unloaded = FrontRod(5, 15, sub=2, payload_kg=0.)
    E0 = unloaded.evaluate(x, T)[0]
    np.testing.assert_allclose(E-E0, .5*9.81*d['points'][-1, 1], atol=1e-10)
    return dict(gradient_directional_error=gradient_error,
                hessian_vector_max_error=hessian_error,
                payload_energy_check_passed=True, nonzero_root_pitch_checked_deg=15.)


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def run(output=None, sub=4):
    output = Path(output) if output else HERE/'results'
    output.mkdir(parents=True, exist_ok=True)
    checks = derivative_check()
    checks.update(kernel_path=str(KERNEL_PATH), kernel_sha256=hashlib.sha256(source.encode()).hexdigest(),
                  kernel_patch="fixed root pitch and explicit UTF-8 text decoding only", finite_search=True,
                  strain_bound=.85, cell_rotation_component_bound_rad=1.5,
                  caution="Search bounds are not measured material limits. No contact, strength or 3D stability certification.")
    (output/'front_validation.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    rows, attempts, arrays = [], [], {}
    drives = [0., .5, 1., 2., 4., 6., 8., 12., 16., 24., 32., 48., 64., 96., 128., 160., 200.]
    for n_uni in (3, 5, 7):
        for pitch in (10, 15, 20):
            r = FrontRod(n_uni, pitch, sub=sub)
            free = r.free_state()
            if free is None:
                attempts.append(dict(configuration=r.label, pitch_deg=pitch,
                                     status='free_sag_not_converged'))
                print(f'{r.label} pitch {pitch}: no free equilibrium', flush=True)
                continue
            for common in (0., 5.):
                for direction in (1, -1):
                    previous = free
                    for force in drives:
                        drive = direction*force
                        T = r.sweep_tensions(drive, common)
                        got = r.solve_force(T, previous)
                        if got is None and force > 0:
                            # Force continuation from the last converged force is
                            # primary; an independent free-sag seed is a fallback.
                            got = r.solve_force(T, free)
                        record = dict(configuration=r.label, pitch_deg=pitch,
                                      signed_drive_n=drive, common_per_rope_n=common,
                                      status='converged' if got is not None else 'not_converged')
                        attempts.append(record)
                        if got is None:
                            continue
                        previous = got
                        metric, points, disks, data = r.metrics(got, T)
                        state_id = f's{len(rows):04d}'
                        metric.update(record, state_id=state_id)
                        rows.append(metric)
                        arrays[state_id+'_x'] = got
                        arrays[state_id+'_points_m'] = points
                        arrays[state_id+'_disks_m'] = disks
                        arrays[state_id+'_theta_rad'] = data['theta']
                        arrays[state_id+'_strain'] = data['eps']
                        arrays[state_id+'_tensions_n'] = T
            print(f'{r.label} pitch {pitch}: {sum(z["configuration"]==r.label and z["pitch_deg"]==pitch for z in rows)} converged records', flush=True)
    write_csv(output/'front_equilibria.csv', rows)
    write_csv(output/'front_attempts.csv', attempts)
    (output/'front_equilibria.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    np.savez_compressed(output/'front_states.npz', **arrays)
    summary = dict(attempts=len(attempts), converged_records=len(rows),
                   configurations=3, pitches_deg=[10, 15, 20], payload_kg=.5,
                   strain_at_most_5_percent=sum(not z['axial_strain_exceeds_5_percent'] for z in rows),
                   stable_planar_records=sum(z['stable_in_plane'] for z in rows),
                   collision_or_material_admissibility_not_evaluated=True)
    (output/'front_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--sub', type=int, default=4)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(derivative_check() if args.check_only else run(args.output_dir, args.sub), indent=2))
