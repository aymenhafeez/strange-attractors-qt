import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit
def _dadras(x_var, t, a, b, c, d, e):
    x, y, z = x_var
    dxdt = y - a * x + b * y * z
    dydt = c * y - x * z + z
    dzdt = d * x * y - e * z

    return [dxdt, dydt, dzdt]


@numba.njit(nogil=True)
def _dadras_lyapunov(x_var, t, params):
    x, y, z = x_var[0], x_var[1], x_var[2]
    a, b, c, d, e = params[0], params[1], params[2], params[3], params[4]

    dxdt = y - a * x + b * y * z
    dydt = c * y - x * z + z
    dzdt = d * x * y - e * z

    return np.array([dxdt, dydt, dzdt])


_dadras_attractor = AttractorConfig(
    "Dadras",
    _dadras,
    lyapunov_equation=_dadras_lyapunov,
    params=[
        AttractorParam("a", 3.0, 0.0, 10.0, 0.01),
        AttractorParam("b", 2.7, 0.0, 30.0, 0.01),
        AttractorParam("c", 1.7, 0.0, 7.40, 0.01),
        AttractorParam("d", 2.0, 0.0, 15.0, 0.01),
        AttractorParam("e", 9.0, 0.0, 15.0, 0.01),
    ],
    initial_conditions=[0.1, 0.03, 0.0],
    time_defaults={"t_min": 0, "t_max": 150, "n": 100000},
    camera_distance=30,
    camera_elevation=20,
    camera_azimuth=25,
    pan=0,
    equation_text=("dx/dt = a·x+b·y·z\ndy/dt = c·y - x·z + z\ndz/dt = d·x·y - e·z"),
    description=(
        "The Dadras system is known for it's multiwing shape. Unlike the Lorenz \
                attractor, the Dadras attractor forms a more compact volume, spiraling \
                around a central core with the wings spreading out around it."
    ),
)
