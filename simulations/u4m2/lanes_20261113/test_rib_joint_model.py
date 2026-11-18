"""Unit checks for rib_joint_model.py (no CAD needed)."""
import numpy as np
import rib_joint_model as R


def square_mesh():
    import shapely.geometry as sg
    return R.mesh_polygon(sg.box(10, -2, 14, 2), 0.2)


def test_cst_rigid_body_modes_have_zero_energy():
    X, T = square_mesh()
    K = R.cst_stiffness(X, T, np.full(len(T), 3.0), 1700., 0.4)
    for u in (np.c_[np.ones(len(X)), np.zeros(len(X))], np.c_[np.zeros(len(X)), np.ones(len(X))],
              np.c_[-X[:, 1], X[:, 0]]):
        assert abs(u.ravel() @ K @ u.ravel()) < 1e-8 * np.abs(K).sum()


def test_cst_uniaxial_patch():
    X, T = square_mesh()
    K = R.cst_stiffness(X, T, np.full(len(T), 3.0), 1700., 0.4)
    u = np.c_[np.zeros(len(X)), 1e-3 * X[:, 1]]           # eps_zz = 1e-3, eps_rr = 0
    energy = 0.5 * u.ravel() @ K @ u.ravel()
    expected = 0.5 * 1700. / (1 - 0.16) * 1e-6 * 16.0 * 3.0  # plane stress, eps_xx = 0
    assert abs(energy / expected - 1) < 1e-9


def test_projection_matches_rigid_motion():
    rng = np.random.default_rng(1)
    for th in (22.5, 67.5, 157.5):
        r0, z0, zc = 19.2, 12.1, 11.9
        w = rng.normal(size=6)
        a, b, beta = R.projection(th, r0, z0, zc) @ w
        t_, om = w[:3], w[3:]
        e_r = np.array([np.cos(np.radians(th)), np.sin(np.radians(th)), 0.]); e_z = np.array([0, 0, 1.])
        for dr, dz in ((0, 0), (0.7, -0.3), (-1.1, 0.4)):
            p = (r0 + dr) * e_r + (z0 + dz - zc) * e_z
            u = t_ + np.cross(om, p)
            assert np.allclose([u @ e_r, u @ e_z], [a - beta * dz, b + beta * dr])


def test_rigid_fit_is_exact_for_rigid_inplane_field():
    rng = np.random.default_rng(2)
    Xp, Er, U2 = [], [], []
    w = rng.normal(size=6); w[5] = 0
    for th in R.MOUNT_ANGLES:
        e_r = np.array([np.cos(np.radians(th)), np.sin(np.radians(th)), 0.])
        for dr, dz in ((0, 0), (1, 0.2), (-1, -0.2), (0.3, 0.25)):
            x = (19.2 + dr) * e_r + np.array([0, 0, 12 + dz]); u = w[:3] + np.cross(w[3:], x)
            Xp.append(x); Er.append(e_r); U2.append([u @ e_r, u[2]])
    res, _ = R.rigid_fit(np.array(Xp), np.array(Er), np.array(U2))
    assert np.abs(res).max() < 1e-10


def test_plate_rigid_modes_from_3d_projection_have_zero_energy():
    import rib_joint_3d as P3
    X, T = square_mesh()
    K = P3.plate_stiffness(X, T, np.full(len(T), 3.0), 1700., 0.4)
    rng = np.random.default_rng(3)
    th = 67.5
    e_r = np.array([np.cos(np.radians(th)), np.sin(np.radians(th)), 0.]); e_z = np.array([0, 0, 1.])
    n = np.cross(e_r, e_z)
    for _ in range(3):
        w = rng.normal(size=6)
        p = np.outer(X[:, 0], e_r) + np.outer(X[:, 1], e_z)
        u = w[:3] + np.cross(w[3:], p)
        # out-of-plane field of a 3D rigid motion: w = n.u ; phi_x = omega.e_z ; phi_y = -omega.e_r
        f = np.c_[u @ n, np.full(len(X), w[3:] @ e_z), np.full(len(X), -(w[3:] @ e_r))]
        assert abs(f.ravel() @ K @ f.ravel()) < 1e-8 * np.abs(K).sum()
        # and the projection6 rows reproduce the master values used by the tie
        P = P3.projection6(th, 0., 0., 0.) @ w
        assert np.allclose(P[3:], [w[:3] @ n, w[3:] @ e_r, w[3:] @ e_z])


def test_plate_pure_bending_patch():
    import rib_joint_3d as P3
    X, T = square_mesh()
    E, nu, t, kx = 1700., 0.4, 3.0, 1e-3
    K = P3.plate_stiffness(X, T, np.full(len(T), t), E, nu)
    x = X[:, 0] - 12.0
    # cylindrical bending w = -kx x^2 / 2, phi_x = kx x  (shear-free), curvature d(phi_x)/dx = kx
    f = np.c_[-kx * x ** 2 / 2, kx * x, np.zeros(len(X))]
    energy = 0.5 * f.ravel() @ K @ f.ravel()
    expected = 0.5 * E * t ** 3 / (12 * (1 - nu ** 2)) * kx ** 2 * 16.0
    assert abs(energy / expected - 1) < 0.02   # linear-triangle shear residual only
