import numba
import numpy as np


def solve_attractor(config, param_values, n=None, t_max=None, ic=None):
    t_def = config.time_defaults
    _t_max = t_max if t_max is not None else t_def["t_max"]
    _n = n or t_def["n"]
    params = np.ascontiguousarray(
        [param_values[p.name] for p in config.params], dtype=np.float64
    )
    y0 = np.ascontiguousarray(
        ic if ic is not None else config.initial_conditions, dtype=np.float64
    )

    return solve_rk4(config.equation, y0, t_def["t_min"], _t_max, _n, params)


@numba.njit(nogil=True)
def _rk4_step(state, dt, params, eq):
    k1 = eq(state, 0.0, params)
    k2 = eq(state + 0.5 * dt * k1, 0.0, params)
    k3 = eq(state + 0.5 * dt * k2, 0.0, params)
    k4 = eq(state + dt * k3, 0.0, params)

    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


@numba.njit(nogil=True)
def solve_rk4(eq, y0, t_min, t_max, n, params):
    state = y0.copy()
    dt = (t_max - t_min) / n
    traj = np.empty((n, y0.shape[0]), dtype=np.float64)

    for i in range(n):
        state = _rk4_step(state, dt, params, eq)
        traj[i] = state

    return traj
