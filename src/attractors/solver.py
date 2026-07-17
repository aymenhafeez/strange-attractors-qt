import numba
import numpy as np
from scipy.integrate import odeint
import threading

from .models import AttractorConfig

_odeint_lock = threading.Lock()


def solve_attractor(
    config: AttractorConfig,
    param_values: dict[str, float],
    n: int | None = None,
    t_max: int | None = None,
    ic: list[float] | None = None,
):
    t_def = config.time_defaults
    _t_max = t_max if t_max is not None else t_def["t_max"]
    t = np.linspace(t_def["t_min"], _t_max, n or t_def["n"])
    params = np.array([param_values[p.name] for p in config.params])
    y0 = ic if ic is not None else config.initial_conditions

    with _odeint_lock:
        return odeint(config.equation, y0, t, args=(params,))


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
