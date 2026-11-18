"""Verification of the finite-rotation shell and the four archived load frames."""

import unittest
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from continuation import transfer_weights
from shell import E, NU, Mesh, Model, element_data, rotation, shell_elements, spin_map
from study import CASES, archive_loads, end_pose, rotpar, surface_extremes
from rib_joint_model import cst_stiffness
from rib_joint_3d import plate_stiffness


class ElementChecks(unittest.TestCase):
    def setUp(self):
        self.xy = np.array([[0.1, 0.2], [1.4, 0.3], [0.2, 1.1]])
        self.triangle = np.array([[0, 1, 2]])
        self.thickness = np.array([2.9])
        self.coefficients, self.material = element_data(self.xy, self.triangle, self.thickness)
        self.flat = np.zeros((3, 6))
        self.flat[:, :2] = self.xy
        self.flat[:, 5] = 1.0

    def response(self, values):
        return shell_elements(values, self.triangle, self.coefficients, self.material, True)

    def test_small_strain_recovers_reference_membrane_and_plate(self):
        energy, grad, hessian, _ = self.response(self.flat)
        self.assertLess(energy[0], 1.0e-20)
        np.testing.assert_allclose(grad, 0.0, atol=3.0e-11)
        membrane = [0, 1, 6, 7, 12, 13]
        plate = [2, 3, 4, 8, 9, 10, 14, 15, 16]
        for indices, routine in ((membrane, cst_stiffness), (plate, plate_stiffness)):
            expected = routine(self.xy, self.triangle, self.thickness, E, NU)
            np.testing.assert_allclose(
                hessian[0][np.ix_(indices, indices)], expected.toarray(), atol=3.0e-10, rtol=1.0e-12
            )
        np.testing.assert_allclose(hessian[0][np.ix_(membrane, plate)], 0.0, atol=3.0e-10)

    def test_shared_node_block_assembly_preserves_the_element_tangent(self):
        triangles = np.repeat(self.triangle, 2, axis=0)
        block_map = np.tile(np.arange(9).reshape(1, 3, 3), (2, 1, 1))
        x = self.flat.copy()
        x[2, :3] += [0.12, -0.06, 0.08]
        _, _, local, _ = self.response(x)
        _, _, blocks, _ = shell_elements(
            x, triangles, self.coefficients, self.material, True, block_map, 9
        )
        expected = local[0].reshape(3, 6, 3, 6).transpose(0, 2, 1, 3).reshape(9, 6, 6)
        np.testing.assert_allclose(blocks, 2.0 * expected, atol=1.0e-10)

    def test_rigid_superposition_on_deformed_triangle(self):
        x = self.flat.copy()
        x[1, :3] += [0.08, -0.06, 0.2]
        x[2, 3:] = Rotation.from_rotvec([0.14, -0.08, 0.03]).apply([0.0, 0.0, 1.0])
        E0, g0, _, strain0 = self.response(x)
        R = Rotation.from_rotvec([1.3, -0.64, 0.35]).as_matrix()
        moved = (x.reshape(-1, 3) @ R.T).reshape(3, 6)
        moved[:, :3] += [11.0, -8.0, 4.0]
        E1, g1, _, strain1 = self.response(moved)
        np.testing.assert_allclose(E1, E0, rtol=2.0e-12)
        np.testing.assert_allclose(strain1, strain0, atol=2.0e-13)
        np.testing.assert_allclose(g1.reshape(-1, 3), g0.reshape(-1, 3) @ R.T, atol=2.0e-10)

    def test_prestressed_tangent_is_energy_derivative(self):
        rng = np.random.default_rng(9602)
        x = self.flat + rng.normal(scale=0.055, size=(3, 6))
        v = rng.normal(size=x.shape)
        v /= np.linalg.norm(v)
        eps = 1.0e-6
        _, gradient, hessian, _ = self.response(x)
        ep, gp, _, _ = self.response(x + eps * v)
        em, gm, _, _ = self.response(x - eps * v)
        np.testing.assert_allclose((ep - em) / (2 * eps), gradient @ v.ravel(), rtol=1.0e-7)
        np.testing.assert_allclose((gp - gm).ravel() / (2 * eps), hessian[0] @ v.ravel(), rtol=1.0e-7)

    def test_face_strain_resolves_tension_compression_and_vertical_build(self):
        mesh = SimpleNamespace(
            thick=np.array([3.0]),
            theta=22.5 + 45.0 * np.arange(8),
            centres=np.array([[18.0, 12.0]]),
            t=self.triangle,
        )
        strains = np.tile([-0.02, 0.06, 0.0, 0.0, 0.01, 0.0], (8, 1))
        output = surface_extremes(mesh, strains)
        self.assertAlmostEqual(output["build_Z_tensile"]["strain"], 0.075)
        self.assertAlmostEqual(output["principal_tensile"]["strain"], 0.075)
        self.assertAlmostEqual(output["principal_compressive"]["strain"], -0.02)
        self.assertAlmostEqual(output["principal_tensile"]["direction_to_build_Z_deg"], 0.0)
        self.assertAlmostEqual(output["principal_compressive"]["direction_to_build_Z_deg"], 90.0)
        self.assertAlmostEqual(output["build_Z_tensile"]["reference_r_z_through_mm"][2], 1.5)

    def test_transfer_preserves_finite_rigid_motion_at_a_free_edge(self):
        edges = np.array([[0.2, 0.2], [1.44, 0.33], [-0.01, 0.25]])
        corners, weights, outside = transfer_weights(self.xy, self.triangle, edges)
        self.assertGreater(outside, 0)
        R = Rotation.from_rotvec([0.7, -0.4, 0.3]).as_matrix()
        src = np.c_[self.xy, np.zeros(3)]
        target = np.c_[edges, np.zeros(3)]
        u = src @ R.T - src + [2.0, -1.0, 0.4]
        np.testing.assert_allclose(
            np.einsum("ij,ijk->ik", weights, u[corners]),
            target @ R.T - target + [2.0, -1.0, 0.4],
            atol=1.0e-12,
        )
        ref = np.cross(src[1] - src[0], src[2] - src[0])[2]
        geometry = SimpleNamespace(tri=self.triangle, reference_area=np.array([ref]))
        self.assertAlmostEqual(Mesh.minimum_orientation(geometry, self.flat), 1.0)
        self.assertAlmostEqual(Mesh.minimum_orientation(geometry, self.flat[[0, 2, 1]]), -1.0)

    def test_rigid_patch_rotation_and_spatial_couple_map(self):
        p = np.array([0.42, -0.26, 0.37])
        v = np.array([0.3, 0.7, -0.6])
        eps = 1.0e-6
        R, dR, ddR = rotation(p)
        Rp, dp, _ = rotation(p + eps * v)
        Rm, dm, _ = rotation(p - eps * v)
        np.testing.assert_allclose((Rp - Rm) / (2 * eps), np.einsum("a,aij->ij", v, dR), atol=2.0e-10)
        np.testing.assert_allclose((dp - dm) / (2 * eps), np.einsum("b,abij->aij", v, ddR), atol=5.0e-10)
        omega = Rotation.from_matrix(Rp @ Rm.T).as_rotvec() / (2 * eps)
        np.testing.assert_allclose(omega, spin_map(p)[0] @ v, atol=2.0e-10)
        np.testing.assert_allclose(rotpar(R), p, atol=1.0e-12)


class AssembledChecks(unittest.TestCase):
    def test_rigid_equivariance_and_loaded_generalized_tangent(self):
        mesh = Mesh(0.6)
        model = Model(mesh, "point")
        p = np.array([0.28, -0.23, 0.16])
        R = rotation(p)[0]
        q = model.zero.copy()
        for body in model.bodies.values():
            q[body.rot] = p
            if body.pos is not None:
                q[body.pos] = (R - np.eye(3)) @ body.centre
        nodes = model.free_nodes
        q[model.free[:, :3]] = mesh.xyz[nodes] @ R.T - mesh.xyz[nodes]
        normals = mesh.directors[nodes]
        d = normals @ R.T
        q[model.free[:, 3:]] = (
            np.einsum("nki,ni->nk", model.free_basis, d)
            / (1.0 + np.einsum("ni,ni->n", normals, d))[:, None]
        )
        x = model.mapping(q)[0]
        np.testing.assert_allclose(x[:, :3], mesh.xyz @ R.T, atol=1.0e-12)
        np.testing.assert_allclose(x[:, 3:], mesh.directors @ R.T, atol=1.0e-12)
        # Perturb one moving seat at this rotated configuration so the geometric
        # stiffness, director mapping and rotation of loaded bore levers are all active.
        guide = model.bodies["G+12"]
        q[guide.pos] += [0.0003, -0.0002, 0.0004]
        model.external = archive_loads()[146]["loads"]
        v = np.zeros_like(q)
        v[guide.pos] = [0.03, 0.08, -0.06]
        v[guide.rot] = [0.007, -0.004, 0.003]
        v[model.free[::31]] = [0.005, -0.008, 0.003, 0.0001, -0.0002]
        eps = 1.0e-6
        _, g, K, _ = model.assemble(q, 1.0)
        ep, gp, _, _ = model.assemble(q + eps * v, 1.0, False)
        em, gm, _, _ = model.assemble(q - eps * v, 1.0, False)
        np.testing.assert_allclose((ep - em) / (2.0 * eps), g @ v, rtol=2.0e-5, atol=2.0e-6)
        numerical = (gp - gm) / (2.0 * eps)
        self.assertLess(np.linalg.norm(numerical - K @ v) / np.linalg.norm(K @ v), 2.0e-5)


class ArchiveChecks(unittest.TestCase):
    def test_all_record_pose_and_simultaneous_hole_totals(self):
        cases = archive_loads()
        self.assertEqual(set(cases), set(CASES))
        for data in cases.values():
            np.testing.assert_allclose(end_pose(data, 0.0), 0.0, atol=1.0e-11)
            expected = np.r_[data["displacement_mm"], rotpar(data["rotation"])]
            np.testing.assert_allclose(end_pose(data, 1.0), expected, atol=1.0e-7)
            self.assertEqual([row["station_mm"] for row in data["checks"]], [-12, 12])
            for row in data["checks"]:
                self.assertEqual(row["holes"], 8)
                for field in ("force_error_N", "moment_error_Nmm", "per_hole_moment_error_Nmm"):
                    self.assertLess(row[field], 1.0e-8)


if __name__ == "__main__":
    unittest.main()
