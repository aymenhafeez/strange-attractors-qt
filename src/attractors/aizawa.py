import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit
def _aizawa(x_var, t, a, b, c, d, e, f):
    x, y, z = x_var

    dxdt = (z - b) * x - d * y
    dydt = d * x + (z - b) * y
    dzdt = c + a * z - (z**3 / 3) - (x**2 + y**2) * (1 + e * z) + (f * z * x**3)

    return [dxdt, dydt, dzdt]


@numba.njit(nogil=True)
def _aizawa_lyapunov(x_var, t, params):
    x, y, z = x_var[0], x_var[1], x_var[2]
    a, b, c, d, e, f = params[0], params[1], params[2], params[3], params[4], params[5]

    dxdt = (z - b) * x - d * y
    dydt = d * x + (z - b) * y
    dzdt = c + a * z - (z**3 / 3) - (x**2 + y**2) * (1 + e * z) + (f * z * x**3)

    return np.array([dxdt, dydt, dzdt])


_aizawa_attractor = AttractorConfig(
    "aizawa",
    _aizawa,
    lyapunov_equation=_aizawa_lyapunov,
    params=[
        AttractorParam("a", 0.95, -0.55, 40.0, 0.01),
        AttractorParam("b", 0.7, -2.0, 25.0, 0.01),
        AttractorParam("c", 0.6, -10.0, 10.0, 0.01),
        AttractorParam("d", 3.5, 0.0, 200.0, 0.01),
        AttractorParam("e", 0.25, 0.0, 60.0, 0.01),
        AttractorParam("f", 0.1, -2.10, 20.0, 0.01),
    ],
    initial_conditions=[0.1, 0.0, 0.0],
    time_defaults={"t_min": 0, "t_max": 30, "n": 100000},
    camera_distance=5,
    camera_elevation=10,
    camera_azimuth=50,
    pan=0.5,
    equation_text=(
        "dx/dt = (z - b)x - d·y\n"
        "dy/dt = d·x + (z - b)y\n"
        "dz/dt = c + a·z - z³/3 - (x² + y²)(1 + e·z) + f·z·x³"
    ),
    description=(
        "The Aizawa attractor differs in shape from the classic winged shape of the "
        "Lorenz or Dadras attractors. Its trajectory seamingly follows the "
        "surface of a sphere while twisting upwards through a funnel shaped "
        "column."
    ),
)
