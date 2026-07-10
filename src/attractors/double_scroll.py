import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _double_scroll(x_var, t, params):
    x, y, z = x_var
    a = params[0]
    b = params[1]
    dxdt = y - 2 * x * z
    dydt = -x + 0.5 * (1 - x**2) * y - 0.5 * y * z
    dzdt = 0.1 * x * y + a * x**2 - 0.8 * b

    return np.array([dxdt, dydt, dzdt])


_double_scroll_attractor = AttractorConfig(
    "double_scroll",
    _double_scroll,
    params=[
        AttractorParam("a", 0.1, 0.0, 5.0, 0.01),
        AttractorParam("b", 0.5, 0.0, 5.0, 0.01),
    ],
    initial_conditions=[0.1, 2, 0.1],
    time_defaults={"t_min": 0, "t_max": 500, "n": 100000},
    camera_distance=5,
    camera_elevation=20,
    camera_azimuth=-40,
    pan=0,
    equation_text=("dx/dt = a(y - x)\ndy/dt = x(b - z)\ndz/dt = x·y - c z"),
    description=(
        "Qiu et al. derived this attractor as a variant of the Sprott A system, with "
        "the addition of cubic nonlinear term in order to construct a novel 3D "
        "chaotic circuit method. While the system has the classic two wings "
        "shown by other attractors, what's unique is that the wings intertwine "
        "and loop into two other downward facing lobes, before looping back up."
    ),
)
