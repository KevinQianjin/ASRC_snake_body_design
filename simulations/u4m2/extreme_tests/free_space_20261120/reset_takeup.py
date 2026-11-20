"""Construct a direction-aware matched-friction reset at the withdrawn clamp."""

import numpy as np


def plan_reset(
    archive, commands, stop, rest, T, wrap, ea, initial_drum, initial_prox, names
):
    length = np.array(
        [[float(r[n + "_internal_path_mm"]) / 1000 for n in names] for r in archive]
    )
    material = length / (1 + T / ea)
    drum = initial_drum.copy()
    raw = commands[-1][2].copy()
    pro = initial_prox.copy()
    result = []

    def move(goal, identifier, kind):
        nonlocal drum, raw
        start = drum.copy()
        count = max(1, int(np.ceil(np.max(abs(goal - start)) / 0.000145)))
        for k in range(1, count + 1):
            f = k / count
            desired = start + (goal - start) * f
            raw = np.where(
                abs(desired - drum) > 1e-12,
                desired + np.sign(desired - drum) * 0.00005,
                raw,
            )
            i, p = identifier(f)
            result.append((i, p, raw.copy(), kind))
            drum = desired

    for prev, nxt in [(-1, stop), *((j, j - 1) for j in range(stop, 0, -1))]:
        delta = material[nxt] - material[prev]
        direction = np.where(abs(delta) > 1e-12, np.sign(delta), 0)

        def proximal(i):
            bound = np.exp(0.15 * wrap[i])
            return np.where(
                direction == 0,
                np.clip(pro, T[i] / bound, T[i] * bound),
                T[i] * bound ** (-direction),
            )

        bridge = prev == -1
        before = material[prev] + 1 / (1 + proximal(prev) / ea)
        move(before, lambda f: (stop if bridge else prev, 1.0), "reset_take_up")
        pro = proximal(nxt)
        goal = material[nxt] + 1 / (1 + pro / ea)
        move(goal, lambda f: (stop, 1.0) if bridge else (prev, 1 - f), "reset_move")
    # Return to equal proximal and distal force inside the static cone. The actual
    # drum first reaches its initial position; removing the play bias then holds it.
    move(rest[0].ravel(), lambda f: (0, 1.0), "equalize_proximal")
    result.append((0, 1.0, rest[0].ravel().copy(), "remove_command_bias"))
    return result
