import numpy as np
from scipy.integrate import odeint


def solve_attractor(config, param_values, n=None, t_max=None):
    t_def = config.time_defaults
    _t_max = t_max if t_max is not None else t_def["t_max"]
    t = np.linspace(t_def["t_min"], _t_max, n or t_def["n"])
    params = np.array([param_values[p.name] for p in config.params])

    return odeint(config.equation, config.initial_conditions, t, args=(params,))
