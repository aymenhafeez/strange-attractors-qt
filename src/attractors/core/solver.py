import numba
import numpy as np


def solve_attractor(config, param_values, n=None, t_max=None, ic=None):
    t_def = config.time_defaults
    _t_max = t_max if t_max is not None else t_def.t_max
    _n = n or t_def.n
    params = np.ascontiguousarray(
        [param_values[p.name] for p in config.params], dtype=np.float64
    )
    y0 = np.ascontiguousarray(
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

        tmp[0] = state[0] + (0.5 * dt) * k1[0]
        tmp[1] = state[1] + (0.5 * dt) * k1[1]
        tmp[2] = state[2] + (0.5 * dt) * k1[2]

        eq(tmp, t + (0.5 * dt), params, k2)

        tmp[0] = state[0] + (0.5 * dt) * k2[0]
        tmp[1] = state[1] + (0.5 * dt) * k2[1]
        tmp[2] = state[2] + (0.5 * dt) * k2[2]
        eq(tmp, t + (0.5 * dt), params, k3)

        tmp[0] = state[0] + dt * k3[0]
        tmp[1] = state[1] + dt * k3[1]
        tmp[2] = state[2] + dt * k3[2]
        eq(tmp, t + dt, params, k4)

        state[0] += (dt / 6.0) * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        state[1] += (dt / 6.0) * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        state[2] += (dt / 6.0) * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])

        traj[i, 0] = state[0]
        traj[i, 1] = state[1]
        traj[i, 2] = state[2]

    return traj
