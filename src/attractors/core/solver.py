# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numba
import numpy as np


def solve_attractor(config, param_values, n=None, t_max=None, ic=None):
    t_def = config.time_defaults
    _t_max = t_max if t_max is not None else t_def.t_max
    _n = n or t_def.n
    params = np.asarray([param_values[p.name] for p in config.params], dtype=np.float64)
    y0 = np.asarray(
        ic if ic is not None else config.initial_conditions, dtype=np.float64
    )

    return solve_rk4(config.equation, y0, t_def.t_min, _t_max, _n, params)


@numba.njit(nogil=True)
def solve_rk4(eq, y0, t_min, t_max, n, params):
    m = y0.shape[0]

    state = y0.copy()
    tmp = np.empty(m, dtype=np.float64)

    k1 = np.empty(m, dtype=np.float64)
    k2 = np.empty(m, dtype=np.float64)
    k3 = np.empty(m, dtype=np.float64)
    k4 = np.empty(m, dtype=np.float64)

    dt = (t_max - t_min) / n
    traj = np.empty((n, m), dtype=np.float64)

    for i in range(n):
        t = t_min + i * dt
        eq(state, t, params, k1)

        for j in range(m):
            tmp[j] = state[j] + 0.5 * dt * k1[j]
        eq(tmp, t + 0.5 * dt, params, k2)

        for j in range(m):
            tmp[j] = state[j] + 0.5 * dt * k2[j]
        eq(tmp, t + 0.5 * dt, params, k3)

        for j in range(m):
            tmp[j] = state[j] + dt * k3[j]
        eq(tmp, t + dt, params, k4)

        for j in range(m):
            state[j] += (dt / 6.0) * (
                k1[j] + 2.0 * k2[j] + 2.0 * k3[j] + k4[j]
            )
            traj[i, j] = state[j]

    return traj
