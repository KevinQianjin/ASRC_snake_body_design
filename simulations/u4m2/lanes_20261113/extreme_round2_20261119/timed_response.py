"""Small-signal timed winch disturbances at two loaded holds, using a conditional mass and damping model."""

import argparse
from pathlib import Path
import numpy as np
from scipy.linalg import eigh, expm
from scipy.spatial.transform import Rotation
from common import OUT, NAMES, trajectory, save
from replay import plant
from closed_loop_cycle import FeedbackDrive


def inertance(rod, z):
    d = rod.kinematic_metrics(z)[1]
    d["points"]
    frames = d["frames"]
    m = rod.mass.copy()
    n = len(z)
    dq = np.eye(n) * 1.0e-5
    dt = np.empty((len(m), 3, n))
    dr = np.empty_like(dt)
    head = np.empty((3, n))
    direction = np.empty((3, n))
    for j, v in enumerate(dq):
        dm, dp = [rod.kinematic_metrics(z + s * v)[1] for s in (-1, 1)]
        diff = (dp["points"] - dm["points"]) / 2.0e-5
        dt[:, :, j] = (diff[:-1] + diff[1:]) / 2
        head[:, j] = diff[-1]
        omega = (
            Rotation.from_matrix(
                dp["frames"] @ dm["frames"].transpose(0, 2, 1)
            ).as_rotvec()
            / 2.0e-5
        )
        dr[:, :, j] = (omega[1:] + omega[:-1]) / 2
        direction[:, j] = (
            rod.R0 @ (dp["frames"][-1, :, 0] - dm["frames"][-1, :, 0]) / 2.0e-5
        )
    r = rod.diameter / 2
    length = rod.l
    inertia = np.diag(
        [r * r / 2, r * r / 4 + length**2 / 12, r * r / 4 + length**2 / 12]
    )
    mid = (
        Rotation.from_matrix(frames[:-1].transpose(0, 2, 1) @ frames[1:]).as_rotvec()
        / 2
    )
    F = frames[:-1] @ Rotation.from_rotvec(mid).as_matrix()
    inertia = F @ inertia @ F.transpose(0, 2, 1)
    M = (
        np.einsum("i,ijk,ijl->kl", m, dt, dt)
        + np.einsum("i,ijk,ijl,ilp->kp", m, dr, inertia, dr)
        + rod.payload * head.T @ head
    )
    return (M + M.T) / 2, head, direction


def response(w, V, source, alpha, mode_count, ramp, lag, damping, delay):
    """First-order winch, damped elastic modes, and a piecewise-linear command with an explicit transport delay."""
    w = w[:mode_count]
    V = V[:, :mode_count]
    gains = V.T @ source
    n = len(w)
    A = np.zeros((2 * n + 3, 2 * n + 3))
    A[:n, n : 2 * n] = np.eye(n)
    A[n : 2 * n, :n] = np.diag(-w * w)
    A[n : 2 * n, n : 2 * n] = np.diag(-2 * damping * w)
    A[n : 2 * n, 2 * n] = gains
    A[-3, -3] = -1 / lag
    A[-3, -2] = 1 / lag
    A[-2, -1] = 1.0
    dt = 0.005
    transition = expm(dt * A)
    times = np.arange(0, 2 * ramp + 4 + delay + dt / 2, dt)
    desired = np.interp(
        times - delay, [0, ramp, ramp + 1.0, 2 * ramp + 1.0], [0.0, 1.0, 1.0, 0.0]
    )
    state = np.zeros(len(A))
    traj = [state.copy()]
    for a, b in zip(desired, desired[1:]):
        state[-1] = (b - a) / dt
        state = transition @ state
        traj.append(state.copy())
    history = np.array(traj)
    return times, desired, history[:, :n] @ V.T, history[:, -3]


def run(out):
    zr, R, T = trajectory()
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    results = []
    for step in (1709, 2432):
        z = zr[step]
        cmd = R[step].ravel()
        t = T[step]
        M, head, direction = inertance(rod, z)
        H = drive.tangent(z, R[step], t.reshape(3, 4))
        values, V = eigh(H, M, subset_by_index=(0, 47))
        if values.min() <= 0:
            raise ValueError(
                "A non-positive eigenvalue requires a separate instability analysis"
            )
        w = np.sqrt(values)
        J = rod.control_jacobian(z)
        amp = -0.00025
        k = NAMES.index("C_up")
        source = J[k] * (drive.ea + t[k]) / cmd[k] * amp
        static = np.linalg.solve(H, source)
        target_tip = head @ static
        for modes in (24, 48):
            for ramp in (0.1, 0.5, 2.0):
                for damping, lag, delay in ((0.02, 0.04, 0.0), (0.10, 0.12, 0.10)):
                    times, desired, disturb, motor = response(
                        w, V, source, amp, modes, ramp, lag, damping, delay
                    )
                    angle = np.linalg.norm(disturb @ direction.T, axis=1) * 180 / np.pi
                    tip = disturb @ head.T
                    track = (
                        np.linalg.norm(tip - desired[:, None] * target_tip, axis=1)
                        * 1000
                    )
                    force = t + (disturb @ J.T) * drive.ea / cmd
                    force[:, k] -= motor * (drive.ea + t[k]) / cmd[k] * amp
                    after = times >= 2 * ramp + 1.0 + delay
                    wrong = np.flatnonzero(
                        after
                        & (
                            np.linalg.norm(tip, axis=1)
                            > 0.05 * max(np.linalg.norm(target_tip), 1e-12)
                        )
                    )
                    settle = (
                        float(times[wrong[-1]] - (2 * ramp + 1 + delay))
                        if len(wrong)
                        else 0.0
                    )
                    if len(wrong) and wrong[-1] == len(times) - 1:
                        settle = None
                    results.append(
                        dict(
                            step=step,
                            rope="C_up",
                            increment_mm=amp * 1000,
                            modes=modes,
                            ramp_s=ramp,
                            damping_ratio=damping,
                            winch_lag_s=lag,
                            transport_delay_s=delay,
                            lowest_modes_Hz=w[:6] / (2 * np.pi),
                            peak_pointing_change_deg=angle.max(),
                            peak_tip_tracking_error_mm=track.max(),
                            minimum_distal_N=force.min(),
                            ringdown_to_5pct_s=settle,
                            static_tip_motion_mm=np.linalg.norm(target_tip) * 1000,
                            omitted_static_tip_fraction=np.linalg.norm(
                                head
                                @ (
                                    static
                                    - V[:, :modes]
                                    @ ((V[:, :modes].T @ source) / values[:modes])
                                )
                            )
                            / np.linalg.norm(target_tip),
                        )
                    )
    save(out / "timed_response.json", results)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
