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
