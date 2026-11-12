"""Four root-operated nylon tendons + a module-clamped plastic backbone.

Independent extension: only READS snake_model.py and craft_data.py. Geometry is
3-D with two bending freedoms at each module and optional axial extension;
independent twist and shear are constrained. SI internally, JSON lengths in mm.
See README_ropes.md for the discretization, constitutive law and limitations.
"""
from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

# Importing the original modules must not regenerate their bytecode files.
sys.dont_write_bytecode = True
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.optimize import minimize, root

import craft_data as D
from snake_model import parse_stack

HERE = Path(__file__).resolve().parent
ROPE_NAMES = ("top", "right", "bottom", "left")
GRAVITY = 9.81


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write_json(path, value):
    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2,
                  default=json_value, allow_nan=False)
        stream.write("\n")


def positive(value, label, allow_zero=False):
    value = float(value)
    if not np.isfinite(value) or (value < 0 if allow_zero else value <= 0):
        raise ValueError(f"{label} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return value


def four_values(values, label):
    a = np.asarray(values, dtype=float)
    if a.shape != (4,) or not np.isfinite(a).all():
        raise ValueError(f"{label} must contain four finite values in {ROPE_NAMES} order")
    return a


def circular_fibers(diameter_m, radial_order=5, angles=24):
    """Area quadrature; Gauss integration in r^2, uniform midpoint azimuths."""
    if radial_order < 2 or angles < 8 or angles % 4:
        raise ValueError("fiber_radial_order >= 2; fiber_angles >= 8 and divisible by 4")
    z, w = leggauss(radial_order)
    radius = diameter_m / 2
    rr = radius * np.sqrt((z + 1) / 2)
    theta = (np.arange(angles) + 0.5) * (2 * np.pi / angles)
    uv = np.stack((rr[:, None] * np.cos(theta),
                   rr[:, None] * np.sin(theta)), axis=-1).reshape(-1, 2)
    weights = np.repeat(w * np.pi * radius ** 2 / (2 * angles), angles)
    return uv, weights


def bend_rotation(a, b):
    """exp(skew([0,-b,a])) and exact derivatives with respect to a,b."""
    k = np.array([[0., -a, -b], [a, 0., 0.], [b, 0., 0.]])
    dk = (np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 0.]]),
          np.array([[0., 0., -1.], [0., 0., 0.], [1., 0., 0.]]))
    t = a*a + b*b
    if t < 1e-6:
        aa = 1 - t/6 + t*t/120 - t*t*t/5040
        bb = 0.5 - t/24 + t*t/720 - t*t*t/40320
        da = -1/6 + t/60 - t*t/1680
        db = -1/24 + t/360 - t*t/13440
    else:
        u = np.sqrt(t)
        aa, bb = np.sin(u)/u, (1 - np.cos(u))/t
        da = (u*np.cos(u) - np.sin(u))/(2*u**3)
        db = (u*np.sin(u) - 2*(1 - np.cos(u)))/(2*t*t)
    kk = k @ k
    rot = np.eye(3) + aa*k + bb*kk
    derivatives = [2*v*da*k + aa*d + 2*v*db*kk + bb*(d@k + k@d)
                   for v, d in zip((a, b), dk)]
    return rot, derivatives


@dataclass
class Control:
    take_up_mm: np.ndarray
    gravity_scale: float = 0.0
    payload_kg: float = 0.0
    engagement: float = 1.0

    @classmethod
    def from_stage(cls, stage):
        return cls(four_values(stage.get("take_up_mm", [0]*4), "take_up_mm"),
                   positive(stage.get("gravity_scale", 1), "gravity_scale", True),
                   positive(stage.get("payload_kg", 0), "payload_kg", True),
                   0.0 if stage.get("free_spool", False) else 1.0)

    def between(self, other, fraction):
        return Control(self.take_up_mm + fraction*(other.take_up_mm-self.take_up_mm),
                       self.gravity_scale + fraction*(other.gravity_scale-self.gravity_scale),
                       self.payload_kg + fraction*(other.payload_kg-self.payload_kg),
                       self.engagement + fraction*(other.engagement-self.engagement))

    def as_dict(self):
        return dict(take_up_mm=self.take_up_mm.tolist(), gravity_scale=self.gravity_scale,
                    payload_kg=self.payload_kg, rope_engagement=self.engagement)


@dataclass
class State:
    x: np.ndarray
    plastic_strain: np.ndarray
    accumulated_plastic_strain: np.ndarray
    control: Control
    dissipated_energy_j: float = 0.0
    accepted_steps: int = 0


class RopeRobot:
    """Discrete module chain, four continuous tendons, one bonded centerline.

    Global X is the initial robot axis; Y points UP; Z is lateral. Each link
    has two material bending angles and an optional scaled axial strain.
    The center backbone has no slip relative to any module end disk. Module
    and backbone section strains therefore coincide. No independent torsion.
    """

    def __init__(self, config, backbone_material, rope_material, *, include_ropes=True):
        self.config = copy.deepcopy(config)
        self.material = copy.deepcopy(backbone_material)
        self.rope_material = copy.deepcopy(rope_material)
        self.include_ropes = bool(include_ropes)
        self.stack = parse_stack(config["stack"])
        if not self.stack:
            raise ValueError("stack must contain at least one module")
        self.n = len(self.stack)
        s = positive(config["module_diameter_mm"], "module_diameter_mm") / D.MODULE_DIAMETER_MM
        length = positive(config.get("module_length_mm", 1000*D.MODULE_LENGTH_M), "module_length_mm") / 1000*s
        self.length = np.full(self.n, length)
        self.reference_length = float(self.length.sum())
        extras = positive(config.get("extras_g_per_module", 0), "extras_g_per_module", True)/1000
        self.module_mass = np.array([D.module_mass_kg(key)*s**3 + extras for key, _ in self.stack])
        self.ei_pos = np.array([D.MODULES[key]["EI_x"]*s**4 for key, _ in self.stack])
        self.ei_neg = np.array([D.MODULES[key]["EI_negx"]*s**4 for key, _ in self.stack])
        self.ei_y = np.array([D.MODULES[key]["EI_y"]*s**4 for key, _ in self.stack])
        self.ea = np.array([D.MODULES[key]["EA"]*s**2 for key, _ in self.stack])
        roll = {"x": 0., "-x": np.pi, "y": np.pi/2, "-y": -np.pi/2}
        angle = np.array([roll[axis] for _, axis in self.stack])
        self.c, self.s = np.cos(angle), np.sin(angle)
        self.c[np.abs(self.c) < 1e-14] = 0
        self.s[np.abs(self.s) < 1e-14] = 0
        solver = config.get("solver", {})
        self.axial = bool(solver.get("axial_compliance", True))
        self.strain_scale = positive(solver.get("axial_strain_scale", .001), "axial_strain_scale")
        self.width = 3 if self.axial else 2
        self.ndof = self.n * self.width
        self.payload_node = config.get("payload_node")
        self.payload_node = self.n if self.payload_node is None else self.payload_node
        if not isinstance(self.payload_node, int) or not 0 <= self.payload_node <= self.n:
            raise ValueError("payload_node must be null (tip) or an integer in 0..n")
        self.moment_tolerance = positive(solver.get("moment_tolerance_nm", 1e-6), "moment tolerance")
        self.force_tolerance = positive(solver.get("axial_force_tolerance_n", .01), "force tolerance")
        self.max_iterations = int(solver.get("max_iterations", 400))
        self.max_subdivisions = int(solver.get("max_subdivisions", 7))
        if self.max_iterations <= 0 or self.max_subdivisions < 0:
            raise ValueError("invalid solver iteration/subdivision settings")

        bc = config["backbone"]
        if bc.get("attachment", "clamped_each_module") != "clamped_each_module":
            raise ValueError("this version implements clamped_each_module only")
        self.backbone_diameter = positive(bc["diameter_mm"], "backbone diameter") / 1000
        self.backbone_area = np.pi*self.backbone_diameter**2/4
        self.backbone_i = np.pi*self.backbone_diameter**4/64
        self.uv, self.area_weights = circular_fibers(
            self.backbone_diameter, int(bc.get("fiber_radial_order", 5)),
            int(bc.get("fiber_angles", 24)))
        self.core_e = self.core_yield = self.core_density = 0.
        if backbone_material:
            if backbone_material.get("role") != "backbone":
                raise ValueError("selected center material is not a backbone material")
            self.core_e = positive(backbone_material["young_modulus_pa"], "backbone E")
            self.core_yield = positive(backbone_material["yield_strength_pa"], "backbone yield")
            self.core_density = positive(backbone_material["density_kg_m3"], "backbone density")
        self.backbone_mass = self.core_density*self.backbone_area*self.length
        self.mass = self.module_mass + self.backbone_mass

        rc = config["ropes"]
        self.rope_diameter = positive(rc["diameter_mm"], "rope diameter")/1000
        self.radius = positive(rc["routing_radius_mm"], "routing radius")/1000
        if self.radius + self.rope_diameter/2 > config["module_diameter_mm"]/2000:
            raise ValueError("routing radius + rope radius exceeds module radius")
        if self.radius < (self.backbone_diameter+self.rope_diameter)/2:
            raise ValueError("the ropes overlap the central backbone")
        if self.rope_diameter > np.sqrt(2)*self.radius:
            raise ValueError("adjacent ropes overlap")
        self.offsets = self.radius*np.array([[0., 1., 0.], [0., 0., 1.],
                                             [0., -1., 0.], [0., 0., -1.]])
        area = np.pi*self.rope_diameter**2/4
        ea_override = rc.get("effective_axial_rigidity_n")
        mass_override = rc.get("effective_linear_density_kg_m")
        self.rope_ea = positive(ea_override if ea_override is not None else
                                rope_material["young_modulus_pa"]*area, "rope effective EA")
        self.rope_linear_mass = positive(mass_override if mass_override is not None else
                                         rope_material["density_kg_m3"]*area, "rope linear density")
        self.pretension = four_values(rc.get("pretension_n", [0]*4), "pretension_n")
        if (self.pretension < 0).any():
            raise ValueError("pretension cannot be negative")
        self.initial_rope_lengths = self.reference_length/(1+self.pretension/self.rope_ea)
        self.rope_segment_mass = (self.rope_linear_mass*self.length[:, None] *
                                  np.ones((1, 4))) if include_ropes else np.zeros((self.n, 4))
        self.inverse_hessian = self._initial_inverse_hessian()

    def _initial_inverse_hessian(self):
        out = np.zeros((self.ndof, self.ndof))
        for i in range(self.n):
            transform = np.array([[self.c[i], self.s[i]], [-self.s[i], self.c[i]]])
            k = transform.T @ np.diag([self.ei_pos[i], self.ei_y[i]]) @ transform
            k = (k + self.core_e*self.backbone_i*np.eye(2))/self.length[i]
            a = i*self.width
            out[a:a+2, a:a+2] = np.linalg.inv(k)
            if self.axial:
                ea = self.ea[i] + self.core_e*self.backbone_area
                out[a+2, a+2] = 1/(ea*self.length[i]*self.strain_scale**2)
        return (out + out.T)/2

    def virgin_state(self):
        return State(np.zeros(self.ndof), np.zeros((self.n, len(self.uv))),
                     np.zeros((self.n, len(self.uv))), Control(np.zeros(4)))

    def angles_and_strain(self, x):
        q = np.asarray(x).reshape(self.n, self.width)
        strain = q[:, 2]*self.strain_scale if self.axial else np.zeros(self.n)
        return q[:, :2], strain

    def geometry(self, x):
        q, strain = self.angles_and_strain(x)
        pts = np.zeros((self.n+1, 3))
        frames = np.zeros((self.n+1, 3, 3)); frames[0] = np.eye(3)
        jp = np.zeros((self.n+1, 3, self.ndof))
        jf = np.zeros((self.n+1, 3, 3, self.ndof))
        for i in range(self.n):
            r, dr = bend_rotation(*q[i])
            frames[i+1] = frames[i] @ r
            jf[i+1] = np.einsum("abk,bc->ack", jf[i], r)
            for j in range(2):
                jf[i+1, :, :, i*self.width+j] += frames[i] @ dr[j]
            current_length = self.length[i]*(1+strain[i])
            pts[i+1] = pts[i] + frames[i+1, :, 0]*current_length
            jp[i+1] = jp[i] + jf[i+1, :, 0, :]*current_length
            if self.axial:
                jp[i+1, :, i*self.width+2] += frames[i+1, :, 0]*self.length[i]*self.strain_scale
        guides = pts[:, None, :] + np.einsum("nij,cj->nci", frames, self.offsets)
        jg = jp[:, None, :, :] + np.einsum("nijk,cj->ncik", jf, self.offsets)
        vectors = np.diff(guides, axis=0)
        lengths = np.linalg.norm(vectors, axis=2)
        if (lengths <= 1e-12).any():
            raise ValueError("degenerate rope guide segment")
        jlength = np.einsum("nci,ncik->ck", vectors/lengths[:, :, None], np.diff(jg, axis=0))
        return dict(pts=pts, frames=frames, guides=guides, point_jac=jp,
                    guide_jac=jg, rope_lengths=lengths.sum(axis=0), rope_length_jac=jlength)

    def fiber_response(self, x, old_plastic):
        q, axial = self.angles_and_strain(x)
        fiber_strain = axial[:, None] - (q/self.length[:, None]) @ self.uv.T
        if not self.material:
            return dict(energy=0., angle_gradient=np.zeros_like(q),
                        axial_gradient=np.zeros(self.n), plastic=old_plastic.copy(),
                        stress=np.zeros_like(fiber_strain), strain=fiber_strain)
        trial = fiber_strain - old_plastic
        elastic_limit = self.core_yield/self.core_e
        elastic_strain = np.clip(trial, -elastic_limit, elastic_limit)
        stress = self.core_e*elastic_strain
        # Incremental potential = recoverable elastic energy + plastic work.
        density = (.5*self.core_e*elastic_strain**2 +
                   self.core_yield*np.maximum(np.abs(trial)-elastic_limit, 0))
        energy = np.sum(density*self.area_weights[None, :]*self.length[:, None])
        return dict(energy=float(energy),
                    angle_gradient=-(stress*self.area_weights) @ self.uv,
                    axial_gradient=np.sum(stress*self.area_weights, axis=1)*self.length,
                    plastic=fiber_strain-elastic_strain, stress=stress, strain=fiber_strain)

    def rope_response(self, geometry, control):
        rest = self.initial_rope_lengths - control.take_up_mm/1000
        if (rest <= 0).any():
            raise ValueError("take-up must be smaller than the rope's unstretched length")
        extension = geometry["rope_lengths"] - rest
        taut_extension = np.maximum(extension, 0)
        engagement = control.engagement if self.include_ropes else 0.
        k = self.rope_ea/rest
        tension = engagement*k*taut_extension
        return dict(rest=rest, extension=extension,
                    strain=taut_extension/rest, tension=tension,
                    energy=float(.5*engagement*np.sum(k*taut_extension**2)),
                    gradient=tension @ geometry["rope_length_jac"])

    def energy_gradient(self, x, old_plastic, control, *, details=False):
        q, axial = self.angles_and_strain(x)
        u = self.c*q[:, 0] + self.s*q[:, 1]
        v = -self.s*q[:, 0] + self.c*q[:, 1]
        kx = np.where(u >= 0, self.ei_pos, self.ei_neg)/self.length
        ky = self.ei_y/self.length
        module_energy = .5*np.sum(kx*u*u + ky*v*v + self.ea*self.length*axial*axial)
        grad = np.zeros((self.n, self.width))
        grad[:, 0] = self.c*kx*u - self.s*ky*v
        grad[:, 1] = self.s*kx*u + self.c*ky*v
        if self.axial:
            grad[:, 2] = self.ea*self.length*axial*self.strain_scale
        fibers = self.fiber_response(x, old_plastic)
        grad[:, :2] += fibers["angle_gradient"]
        if self.axial:
            grad[:, 2] += fibers["axial_gradient"]*self.strain_scale
        geo = self.geometry(x)
        ropes = self.rope_response(geo, control)
        mids = .5*(geo["pts"][:-1] + geo["pts"][1:])
        jmids = .5*(geo["point_jac"][:-1] + geo["point_jac"][1:])
        rope_mids = .5*(geo["guides"][:-1] + geo["guides"][1:])
        jrmids = .5*(geo["guide_jac"][:-1] + geo["guide_jac"][1:])
        g = GRAVITY*control.gravity_scale
        gravity_energy = g*(self.mass @ mids[:, 1] +
                            control.payload_kg*geo["pts"][self.payload_node, 1] +
                            np.sum(self.rope_segment_mass*rope_mids[:, :, 1]))
        gravity_gradient = g*(self.mass @ jmids[:, 1, :] +
                              control.payload_kg*geo["point_jac"][self.payload_node, 1, :] +
                              np.einsum("nc,nck->k", self.rope_segment_mass, jrmids[:, :, 1, :]))
        total_gradient = grad.ravel() + ropes["gradient"] + gravity_gradient
        energy = float(module_energy + fibers["energy"] + ropes["energy"] + gravity_energy)
        if details:
            return energy, total_gradient, dict(geometry=geo, ropes=ropes, fibers=fibers,
                                                module_energy_j=float(module_energy),
                                                gravity_energy_j=float(gravity_energy))
        return energy, total_gradient

    def residuals(self, gradient):
        grad = gradient.reshape(self.n, self.width)
        moment = float(np.max(np.abs(grad[:, :2])))
        force = float(np.max(np.abs(grad[:, 2]/(self.strain_scale*self.length)))) if self.axial else 0.
        return moment, force

    def _solve_step(self, state, control):
        fun = lambda x: self.energy_gradient(x, state.plastic_strain, control)
        opt = minimize(fun, state.x, jac=True, method="BFGS", options=dict(
            gtol=2e-10, maxiter=self.max_iterations, hess_inv0=self.inverse_hessian.copy()))
        x = opt.x
        energy, grad, data = self.energy_gradient(x, state.plastic_strain, control, details=True)
        moment, force = self.residuals(grad)
        if moment > self.moment_tolerance or force > self.force_tolerance:
            refined = root(lambda a: fun(a)[1], x, method="hybr", options=dict(xtol=1e-10))
            re, rg = fun(refined.x)
            rm, rf = self.residuals(rg)
            # The stationary refinement must remain on the nearby minimum.
            if np.isfinite(re) and re <= energy + 1e-8 and rm < moment and rf <= max(force, self.force_tolerance):
                x, energy, grad = refined.x, re, rg
                moment, force = rm, rf
                _, _, data = self.energy_gradient(x, state.plastic_strain, control, details=True)
        q, strain = self.angles_and_strain(x)
        if (not np.isfinite(x).all() or moment > self.moment_tolerance or
                force > self.force_tolerance or np.max(np.abs(strain)) > .05 or
                np.max(np.linalg.norm(q, axis=1)) >= np.pi*.9):
            raise RuntimeError(f"equilibrium failed: moment residual={moment:.3g} Nm, "
                               f"axial residual={force:.3g} N; {opt.message}")
        plastic = data["fibers"]["plastic"]
        increment = np.abs(plastic-state.plastic_strain)
        dissipation = self.core_yield*np.sum(increment*self.area_weights*self.length[:, None])
        # Plastic history is committed once, only after successful equilibrium.
        return State(x.copy(), plastic.copy(), state.accumulated_plastic_strain+increment,
                     control, state.dissipated_energy_j+float(dissipation), state.accepted_steps+1)

    def advance(self, state, target, depth=0):
        try:
            return self._solve_step(state, target)
        except RuntimeError:
            if depth >= self.max_subdivisions:
                raise
            middle = state.control.between(target, .5)
            halfway = self.advance(state, middle, depth+1)
            return self.advance(halfway, target, depth+1)

    def stability_eigenvalue(self, state):
        """Local constrained stability in scaled coordinates, at committed state."""
        h = np.empty((self.ndof, self.ndof))
        step = 2e-6
        for j in range(self.ndof):
            dx = np.zeros(self.ndof); dx[j] = step
            gp = self.energy_gradient(state.x+dx, state.plastic_strain, state.control)[1]
            gm = self.energy_gradient(state.x-dx, state.plastic_strain, state.control)[1]
            h[:, j] = (gp-gm)/(2*step)
        return float(np.linalg.eigvalsh((h+h.T)/2)[0])

    def result(self, state, stage):
        _, grad, data = self.energy_gradient(state.x, state.plastic_strain, state.control, details=True)
        q, axial = self.angles_and_strain(state.x)
        moment, force = self.residuals(grad)
        eigen = self.stability_eigenvalue(state)
        if eigen < -1e-5:
            raise RuntimeError(f"{stage}: equilibrium has a negative stability eigenvalue {eigen:.3g}")
        tip = data["geometry"]["pts"][-1]
        plastic_links = np.max(state.accumulated_plastic_strain, axis=1) > 1e-10
        plastic_curvature = -(state.plastic_strain*self.area_weights) @ self.uv/self.backbone_i
        tensions = data["ropes"]["tension"]
        spool_free = state.control.engagement == 0
        control_mode = ("no_ropes" if not self.include_ropes else
                        "free_spool" if spool_free else "fixed_length")
        # A transverse displacement is residual only when external forces have
        # been removed. Zero winch command alone does not imply zero tension.
        unloaded = state.control.gravity_scale == 0 and np.all(tensions <= 1e-8)
        strain_warning = float(self.config["ropes"].get("strain_warning_fraction", .02))
        warnings = []
        if self.include_ropes and not spool_free and np.max(data["ropes"]["strain"]) > strain_warning:
            warnings.append("rope strain exceeds the configured small-strain screening threshold")
        if np.max(np.linalg.norm(q, axis=1)) > .5:
            warnings.append("large bending per module: refine discretization / verify guide geometry")
        summary = dict(material=self.material["id"] if self.material else "modules_only",
                       assembly_name=self.config.get("assembly_name", "custom"),
                       scenario_name=self.config.get("scenario_name", "no_extra_payload"),
                       module_count=self.n,
                       payload_kg=state.control.payload_kg,
                       payload_node=self.payload_node,
                       payload_force_n=GRAVITY*state.control.gravity_scale*state.control.payload_kg,
                       gravity_scale=state.control.gravity_scale,
                       stage=stage, ok=True, tip_x_mm=float(tip[0]*1000),
                       tip_y_mm=float(tip[1]*1000), tip_z_mm=float(tip[2]*1000),
                       tip_drop_mm=float(-tip[1]*1000),
                       transverse_tip_mm=float(np.linalg.norm(tip[1:])*1000),
                       residual_tip_mm=float(np.linalg.norm(tip[1:])*1000) if unloaded else None,
                       rope_control_mode=control_mode,
                       reference_length_mm=self.reference_length*1000,
                       current_length_mm=float(np.sum(self.length*(1+axial))*1000),
                       total_mass_g=float((self.mass.sum()+self.rope_segment_mass.sum())*1000),
                       system_mass_g=float((self.mass.sum()+self.rope_segment_mass.sum()+state.control.payload_kg)*1000),
                       backbone_mass_g=float(self.backbone_mass.sum()*1000),
                       rope_mass_g=float(self.rope_segment_mass.sum()*1000),
                       max_joint_deg=float(np.degrees(np.linalg.norm(q, axis=1)).max()),
                       max_axial_strain=float(np.max(np.abs(axial))),
                       plastic_module_count=int(plastic_links.sum()),
                       max_accumulated_plastic_strain=float(state.accumulated_plastic_strain.max()),
                       dissipated_energy_j=state.dissipated_energy_j,
                       moment_residual_nm=moment, axial_force_residual_n=force,
                       min_stability_eigenvalue=eigen, accepted_steps=state.accepted_steps,
                       warnings="; ".join(warnings))
        for name, tension in zip(ROPE_NAMES, tensions):
            summary[f"tension_{name}_n"] = float(tension)
        for name, command in zip(ROPE_NAMES, state.control.take_up_mm):
            summary[f"take_up_{name}_mm"] = float(command) if control_mode == "fixed_length" else None
            summary[f"take_up_change_{name}_mm"] = None
        # A free spool pays out enough rope to eliminate tension; the geometrical
        # excess over the old locked length is NOT actual elastic strain then.
        rope_strain = data["ropes"]["strain"] if not spool_free else np.zeros(4)
        return dict(summary=summary, control=state.control.as_dict(),
                    pts_m=data["geometry"]["pts"], frames=data["geometry"]["frames"],
                    rope_guides_m=data["geometry"]["guides"],
                    rope_path_length_m=data["geometry"]["rope_lengths"],
                    locked_rope_rest_length_m=data["ropes"]["rest"],
                    rope_elastic_strain=rope_strain,
                    rope_tension_n=tensions, joint_bend_rad=q, axial_strain=axial,
                    plastic_curvature_per_m=plastic_curvature,
                    fiber_plastic_strain=state.plastic_strain,
                    fiber_accumulated_plastic_strain=state.accumulated_plastic_strain,
                    backbone_stress_pa=data["fibers"]["stress"],
                    state_x=state.x)

    def run(self, protocol, *, progress=None):
        state = self.virgin_state()
        results = []
        names = set()
        for stage in protocol:
            name = stage["name"]
            if not name or name in names:
                raise ValueError("protocol stage names must be nonempty and unique")
            names.add(name)
            target = Control.from_stage(stage)
            steps = int(stage.get("steps", 16))
            if steps <= 0:
                raise ValueError("stage steps must be positive")
            start = state.control
            for fraction in np.linspace(1/steps, 1, steps):
                state = self.advance(state, start.between(target, fraction))
            result = self.result(state, name)
            if result["summary"]["rope_control_mode"] == "fixed_length" and start.engagement == 1:
                for rope, change in zip(ROPE_NAMES, target.take_up_mm-start.take_up_mm):
                    result["summary"][f"take_up_change_{rope}_mm"] = float(change)
            results.append(result)
            if progress:
                progress(result["summary"])
        return results


def backbone_properties(material, diameter_mm):
    d = positive(diameter_mm, "diameter")/1000
    area, inertia = np.pi*d*d/4, np.pi*d**4/64
    e, y = material["young_modulus_pa"], material["yield_strength_pa"]
    return dict(material=material["id"], label=material["label"],
                young_modulus_gpa=e/1e9, yield_strength_mpa=y/1e6,
                density_kg_m3=material["density_kg_m3"],
                bending_rigidity_nm2=e*inertia,
                first_yield_moment_nm=y*inertia/(d/2),
                fully_plastic_moment_nm=y*d**3/6,
                first_yield_curvature_per_m=y/(e*d/2),
                linear_mass_g_m=material["density_kg_m3"]*area*1000)


def open_database(path, seed):
    """JSON is the editable catalog; synchronize its records into SQLite."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
            note TEXT NOT NULL, checked_on TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY, role TEXT NOT NULL, label TEXT NOT NULL,
            temper TEXT NOT NULL, young_modulus_pa REAL NOT NULL,
            density_kg_m3 REAL NOT NULL, yield_strength_pa REAL,
            calibrated INTEGER NOT NULL, properties_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS property_sources (
            material_id TEXT NOT NULL REFERENCES materials(id),
            property_name TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
            PRIMARY KEY(material_id, property_name));
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL, config_json TEXT NOT NULL,
            catalog_json TEXT NOT NULL, original_sha256_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
            material_id TEXT NOT NULL, stage TEXT NOT NULL, tip_drop_mm REAL NOT NULL,
            tip_z_mm REAL NOT NULL, max_tension_n REAL NOT NULL,
            plastic_module_count INTEGER NOT NULL, ok INTEGER NOT NULL,
            summary_json TEXT NOT NULL, result_json TEXT NOT NULL,
            UNIQUE(run_id, material_id, stage));
    """)
    # Add new readable result columns without deleting previous runs or the
    # internal constitutive history kept by older versions.
    case_columns = {row[1] for row in con.execute("PRAGMA table_info(cases)")}
    additions = {"residual_tip_mm": "REAL", "rope_control_mode": "TEXT",
                 "scenario_name": "TEXT", "payload_kg": "REAL",
                 "payload_node": "INTEGER", "payload_force_n": "REAL",
                 **{f"take_up_{name}_mm": "REAL" for name in ROPE_NAMES},
                 **{f"take_up_change_{name}_mm": "REAL" for name in ROPE_NAMES}}
    for name, column_type in additions.items():
        if name not in case_columns:
            con.execute(f"ALTER TABLE cases ADD COLUMN {name} {column_type}")
    for source in seed["sources"]:
        con.execute("""INSERT INTO sources VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,url=excluded.url,note=excluded.note,checked_on=excluded.checked_on""",
                    (source["id"], source["title"], source["url"], source["note"], seed["checked_on"]))
    source_ids = {a["id"] for a in seed["sources"]}
    seen = set()
    for material in seed["materials"]:
        if material["id"] in seen:
            raise ValueError("duplicate material identifier")
        seen.add(material["id"])
        positive(material["young_modulus_pa"], "material E")
        positive(material["density_kg_m3"], "material density")
        if material["role"] == "backbone":
            positive(material["yield_strength_pa"], "backbone yield strength")
        con.execute("""INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET role=excluded.role,label=excluded.label,
            temper=excluded.temper,young_modulus_pa=excluded.young_modulus_pa,
            density_kg_m3=excluded.density_kg_m3,yield_strength_pa=excluded.yield_strength_pa,
            calibrated=excluded.calibrated,properties_json=excluded.properties_json""",
                    (material["id"], material["role"], material["label"], material["temper"],
                     material["young_modulus_pa"], material["density_kg_m3"],
                     material.get("yield_strength_pa"), int(material.get("calibrated", False)),
                     json.dumps(material, ensure_ascii=False)))
        con.execute("DELETE FROM property_sources WHERE material_id=?", (material["id"],))
        for prop, source_id in material["property_sources"].items():
            if source_id not in source_ids:
                raise ValueError(f"missing source {source_id}")
            con.execute("INSERT INTO property_sources VALUES (?,?,?)", (material["id"], prop, source_id))
    con.commit()
    return con


def database_materials(con):
    return {key: json.loads(body) for key, body in con.execute("SELECT id,properties_json FROM materials")}


def original_hashes():
    return {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
            for name in ("snake_model.py", "craft_data.py")}


def print_case(summary):
    residual = summary["residual_tip_mm"]
    residual_label = f"{residual:.3f} mm" if residual is not None else "-- (loaded)"
    print(f"  {summary['stage']:21s} drop={summary['tip_drop_mm']:9.3f} mm"
          f"  lateral={summary['tip_z_mm']:9.3f} mm  residual={residual_label}")
    print(f"    payload: {summary['payload_kg']*1000:.1f} g at node {summary['payload_node']}"
          f"; downward force={summary['payload_force_n']:.3f} N"
          f"; gravity_scale={summary['gravity_scale']:.2f}")
    mode = summary["rope_control_mode"]
    if mode == "fixed_length":
        commands = ", ".join(f"{name}={summary[f'take_up_{name}_mm']:+.2f}" for name in ROPE_NAMES)
        print(f"    take_up [mm, from initial]: {commands}")
        if summary["take_up_change_top_mm"] is not None:
            moves = ", ".join(f"{name}={summary[f'take_up_change_{name}_mm']:+.2f}" for name in ROPE_NAMES)
            print(f"    move [mm, this stage]:     {moves}")
        else:
            print("    move: re-locking after free spool; prior free payout is not a fixed-length command")
    elif mode == "free_spool":
        print("    take_up: free_spool (all four winches released; no prescribed length)")
    else:
        print("    take_up: n/a (modules-only baseline has no ropes)")
    tensions = ", ".join(f"{name}={summary[f'tension_{name}_n']:.2f}" for name in ROPE_NAMES)
    print(f"    T [N]: {tensions}", flush=True)
    if summary["warnings"]:
        print(f"    warning: {summary['warnings']}", flush=True)


def save_outputs(output_dir, config, seed, cases, properties, con, before):
    output_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()
    body = dict(created_utc=created, config=config, material_catalog=seed,
                original_sha256=before, backbone_properties=properties, cases=cases,
                model_scope="3D bending + axial strain, no independent twist/shear/contact; reference materials")
    write_json(output_dir/"comparison.json", body)
    rows = [case["summary"] for case in cases]
    with (output_dir/"comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [key for key in rows[0] if key not in
                  ("plastic_module_count", "max_accumulated_plastic_strain")]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    with (output_dir/"backbone_properties.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(properties[0]))
        writer.writeheader(); writer.writerows(properties)
    with con:
        cursor = con.execute("INSERT INTO runs(created_utc,config_json,catalog_json,original_sha256_json) VALUES(?,?,?,?)",
                             (created, json.dumps(config, ensure_ascii=False),
                              json.dumps(seed, ensure_ascii=False), json.dumps(before)))
        run_id = cursor.lastrowid
        for case in cases:
            s = case["summary"]
            con.execute("""INSERT INTO cases(run_id,material_id,stage,tip_drop_mm,tip_z_mm,
                max_tension_n,plastic_module_count,ok,summary_json,result_json,
                residual_tip_mm,rope_control_mode,take_up_top_mm,take_up_right_mm,
                take_up_bottom_mm,take_up_left_mm,take_up_change_top_mm,
                take_up_change_right_mm,take_up_change_bottom_mm,take_up_change_left_mm,
                scenario_name,payload_kg,payload_node,payload_force_n)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (run_id, s["material"], s["stage"], s["tip_drop_mm"], s["tip_z_mm"],
                         max(s[f"tension_{name}_n"] for name in ROPE_NAMES),
                         s["plastic_module_count"], int(s["ok"]),
                         json.dumps(s, ensure_ascii=False),
                         json.dumps(case, ensure_ascii=False, default=json_value, allow_nan=False),
                         s["residual_tip_mm"], s["rope_control_mode"],
                         *[s[f"take_up_{name}_mm"] for name in ROPE_NAMES],
                         *[s[f"take_up_change_{name}_mm"] for name in ROPE_NAMES],
                         s["scenario_name"], s["payload_kg"], s["payload_node"], s["payload_force_n"]))
    return run_id


def make_plots(output_dir, cases, config, properties):
    # Keep all Matplotlib-generated files inside the new output directory.
    os.environ.setdefault("MPLCONFIGDIR", str(output_dir/".mplconfig"))
    os.environ.setdefault("XDG_CACHE_HOME", str(output_dir/".cache"))
    (Path(os.environ["XDG_CACHE_HOME"])/"fontconfig").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    from matplotlib.ticker import MaxNLocator

    material_ids = [p["material"] for p in properties]
    labels = {p["material"]: p["label"] for p in properties}
    lookup = {(c["summary"]["material"], c["summary"]["stage"]): c for c in cases}
    stages = [s["name"] for s in config["protocol"]]
    colors = plt.get_cmap("tab10")
    stage_labels = {"self_weight": "Self-weight / winches locked",
                    "tip_payload_500g": "Tip +500 g / winches locked",
                    "pull_top_10mm": "Top +10 mm / bottom -10 mm",
                    "pull_top_right": "Top/right pull / opposite payout",
                    "return_zero": "All winches return to zero",
                    "free_spool": "Free spool / gravity on",
                    "payload_removed": "500 g removed / gravity on",
                    "unloaded_residual": "Residual / gravity off"}
    if "tip_payload_500g" in stages:
        stage_labels["self_weight"] = "Self-weight / before payload"
        stage_labels["free_spool"] = "Free spool / 500 g remains"
        stage_labels["unloaded_residual"] = "Residual / payload + gravity off"
    stage_colors = {"self_weight": 0, "pull_top_10mm": 1, "pull_top_right": 2,
                    "return_zero": 3, "free_spool": 4, "unloaded_residual": 5,
                    "tip_payload_500g": 6, "payload_removed": 7}
    # Use identical limits and physical scale for all three materials.
    points = np.concatenate([np.asarray(c["pts_m"])*1000 for c in cases
                             if c["summary"]["material"] in material_ids])
    low, high = points.min(axis=0), points.max(axis=0)
    padding = np.maximum((high-low)*.06, 10.)
    low, high = low-padding, high+padding
    fig = plt.figure(figsize=(6.8*len(material_ids), 7))
    fig.subplots_adjust(left=.01, right=.99, top=.79, bottom=.10, wspace=.08)
    for i, material in enumerate(material_ids):
        ax = fig.add_subplot(1, len(material_ids), i+1, projection="3d")
        for j, stage in enumerate(stages):
            case = lookup[(material, stage)]
            pts = np.asarray(case["pts_m"])*1000
            # Plot horizontal world X/Z, vertical world Y.
            ax.plot(pts[:, 0], pts[:, 2], pts[:, 1], color=colors(stage_colors.get(stage, j)),
                    label=stage_labels.get(stage, stage), lw=2)
        ax.set_title(labels[material], pad=12)
        # Place labels inside the axes: 3-D auto labels can be clipped by savefig.
        ax.text2D(.48, .035, "X axial (mm)", transform=ax.transAxes, ha="center")
        ax.text2D(.88, .09, "Z lateral (mm)", transform=ax.transAxes, rotation=48, ha="center")
        ax.text2D(1.05, .53, "Y up (mm)", transform=ax.transAxes, rotation=90, ha="center")
        ax.set(xlim=(low[0], high[0]), ylim=(low[2], high[2]), zlim=(low[1], high[1]))
        ax.set_box_aspect((high-low)[[0, 2, 1]])
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_major_locator(MaxNLocator(4))
        if (high[2]-low[2]) < .15*(high[0]-low[0]):
            # At physical scale a narrow lateral axis cannot fit four labels.
            ax.set_yticks([0.])
        ax.view_init(elev=25, azim=-65)
    handles, legend_labels = ax.get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", bbox_to_anchor=(.5, .95),
               ncol=3, fontsize=10, frameon=False)
    fig.suptitle("Four nylon tendons + module-clamped passive backbone | sequential history | same physical scale", y=.99)
    fig.savefig(output_dir/"shapes_3d.png", dpi=170, bbox_inches="tight", pad_inches=.3)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    ax = axes[0, 0]
    radius = config["module_diameter_mm"]/2
    ax.add_patch(Circle((0, 0), radius, fill=False, color="#64748b", lw=2))
    ax.add_patch(Circle((0, 0), config["backbone"]["diameter_mm"]/2, color="#94a3b8"))
    r = config["ropes"]["routing_radius_mm"]
    # Display right along +Z and up along +Y.
    for j, (name, z, y) in enumerate(zip(ROPE_NAMES, [0, r, 0, -r], [r, 0, -r, 0])):
        ax.add_patch(Circle((z, y), config["ropes"]["diameter_mm"]/2, color=colors(j)))
        ax.annotate(name, (z, y), xytext=(z+1.5, y+1.5), fontsize=9)
    ax.plot([0, r], [0, 0], "--", color="#64748b")
    ax.text(r/2, -2, f"r = {r:g} mm", ha="center")
    ax.set(xlim=(-radius-5, radius+8), ylim=(-radius-5, radius+5), aspect="equal",
           xlabel="Z (mm)", ylabel="Y (mm)", title="Cross-section (rope diameter 2 mm; core 4.2 mm)")
    ax.grid(alpha=.2)
    x = np.arange(len(material_ids))
    stage = ("tip_payload_500g" if "tip_payload_500g" in stages else
             "self_weight" if "self_weight" in stages else stages[0])
    axes[0, 1].bar(x, [lookup[(m, stage)]["summary"]["tip_drop_mm"] for m in material_ids],
                   color=[colors(i) for i in x])
    drop_title = "Tip drop: 500 g at tip" if stage == "tip_payload_500g" else f"Tip drop: {stage}"
    axes[0, 1].set(title=drop_title, ylabel="Downward displacement (mm)",
                   xticks=x, xticklabels=[labels[m] for m in material_ids])
    ax = axes[1, 0]
    stage = "pull_top_right" if "pull_top_right" in stages else stages[-1]
    for j, name in enumerate(ROPE_NAMES):
        ax.bar(x + (j-1.5)*.18, [lookup[(m, stage)]["summary"][f"tension_{name}_n"] for m in material_ids],
               width=.18, label=name, color=colors(j))
    ax.set(title=f"Four tendon tensions: {stage}", ylabel="Tension (N)",
           xticks=x, xticklabels=[labels[m] for m in material_ids])
    ax.legend()
    ax = axes[1, 1]
    residual = "unloaded_residual" if "unloaded_residual" in stages else stages[-1]
    ax.bar(x, [lookup[(m, residual)]["summary"]["transverse_tip_mm"] for m in material_ids],
           color=[colors(i) for i in x])
    ax.set(title=f"Transverse tip displacement: {residual}", ylabel="sqrt(Y tip^2 + Z tip^2) (mm)",
           xticks=x, xticklabels=[labels[m] for m in material_ids])
    for ax in axes.flat:
        if ax is not axes[0, 0]:
            ax.grid(axis="y", alpha=.2)
            ax.set_axisbelow(True)
    fig.suptitle("Reference screening results | PA6 rope stiffness and metal plasticity require calibration")
    fig.savefig(output_dir/"comparison.png", dpi=170)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE/"rope_config.json")
    parser.add_argument("--catalog", type=Path, default=(HERE.parents[2] / 'data' / 'materials' / 'rope_materials.json'))
    parser.add_argument("--database", type=Path, default=(HERE.parents[2] / 'data' / 'materials' / 'rope_materials.sqlite3'))
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="output directory; otherwise use config output_directory or rope_results")
    parser.add_argument("--material", default="all", help="all, or comma-separated backbone material IDs")
    parser.add_argument("--list-materials", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    config, seed = read_json(args.config), read_json(args.catalog)
    before = original_hashes()
    con = open_database(args.database, seed)
    try:
        catalog = database_materials(con)
        selected = config["backbone"]["materials"] if args.material == "all" else args.material.split(",")
        properties = []
        for key in selected:
            if key not in catalog or catalog[key]["role"] != "backbone":
                raise ValueError(f"unknown backbone material {key!r}")
            properties.append(backbone_properties(catalog[key], config["backbone"]["diameter_mm"]))
        if not properties or len(set(selected)) != len(selected):
            raise ValueError("select at least one material, without duplicates")
        print("Backbone reference database (solid circular section):")
        print(f"{'material':21s} {'E [GPa]':>9s} {'yield [MPa]':>12s} {'EI [Nm2]':>10s} {'My [Nm]':>10s} {'g/m':>9s}")
        for p in properties:
            print(f"{p['material']:21s} {p['young_modulus_gpa']:9.2f} {p['yield_strength_mpa']:12.2f}"
                  f" {p['bending_rigidity_nm2']:10.4f} {p['first_yield_moment_nm']:10.4f} {p['linear_mass_g_m']:9.2f}")
        if args.list_materials:
            return 0
        rope = catalog[config["ropes"]["material"]]
        if rope["role"] != "rope":
            raise ValueError("ropes.material must identify a rope material")
        if not config.get("protocol"):
            raise ValueError("protocol must contain at least one stage")
        print(f"\nAssembly {config.get('assembly_name', 'custom')}: {config['stack']}")
        print(f"Scenario: {config.get('scenario_name', 'no_extra_payload')}")
        print("\nRope names: top / right / bottom / left. Positive drop = downward.")
        print("take_up [mm]: cumulative from initial; positive = take up, negative = pay out.")
        print("move [mm]: change from the previous locked-length stage; same sign convention.")
        print("residual [mm]: sqrt(Y_tip^2 + Z_tip^2), after zero gravity and zero rope tension only.")
        print("'-- (loaded)' means the current displacement is not an unloaded residual.")
        print("Rope EA uses a PA6 solid-stock surrogate unless explicitly overridden; results are not calibrated.", flush=True)
        cases = []
        # Baseline uses the original model's inextensible, module-only assumptions.
        baseline_config = copy.deepcopy(config)
        baseline_config["solver"]["axial_compliance"] = False
        baseline = RopeRobot(baseline_config, None, rope, include_ropes=False)
        print("\nModules-only baseline (no center backbone or ropes):", flush=True)
        first = copy.deepcopy(config["protocol"][0])
        first.update(name="self_weight", take_up_mm=[0]*4, free_spool=True)
        cases.extend(baseline.run([first], progress=print_case))
        for material in selected:
            robot = RopeRobot(config, catalog[material], rope)
            print(f"\n{material}: {robot.n} modules, {robot.reference_length*1000:.1f} mm, "
                  f"routing radius {robot.radius*1000:.1f} mm", flush=True)
            cases.extend(robot.run(config["protocol"], progress=print_case))
        if original_hashes() != before:
            raise RuntimeError("original source files changed during the run")
        output_dir = (args.output_dir if args.output_dir is not None else
                      HERE/config.get("output_directory", "rope_results")).resolve()
        run_id = save_outputs(output_dir, config, seed, cases, properties, con, before)
        if not args.no_plots:
            make_plots(output_dir, cases, config, properties)
        print(f"\nSaved run {run_id}: {output_dir}")
        print(f"SQLite database: {args.database.resolve()}")
        print("Original source SHA256 checksums unchanged.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
