import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit
def _lorenz84(x_var, t, a, b, c, d):
    x, y, z = x_var
    dxdt = -a * x - y**2 - z**2 + a * c
    dydt = -y + x * y - b * x * z + d
    dzdt = -z + b * x * y + x * z

    return [dxdt, dydt, dzdt]


@numba.njit(nogil=True)
def _lorenz84_lyapunov(x_var, t, params):
    x, y, z = x_var[0], x_var[1], x_var[2]
    a, b, c, d = params[0], params[1], params[2], params[3]

    dxdt = -a * x - y**2 - z**2 + a * c
    dydt = -y + x * y - b * x * z + d
    dzdt = -z + b * x * y + x * z

    return np.array([dxdt, dydt, dzdt])


_lorenz84_attractor = AttractorConfig(
    "lorenz84",
    _lorenz84,
    lyapunov_equation=_lorenz84_lyapunov,
    params=[
        AttractorParam("a", 0.25, 0.0, 75.0, 0.01),
        AttractorParam("b", 4.0, 0.0, 150.0, 0.01),
        AttractorParam("c", 8.0, 0.0, 20.0, 0.01),
        AttractorParam("d", 1.0, 0.0, 20.0, 0.01),
    ],
    initial_conditions=[0.1, 0.0, 0.0],
    time_defaults={"t_min": 0, "t_max": 150, "n": 30000},
    camera_distance=7,
    camera_elevation=10,
    camera_azimuth=5,
    pan=0,
    equation_text=(
        "dx/dt = -a·x - y² - z² + a·c\n"
        "dy/dt = -y + x·y - b·x·z + d\n"
        "dz/dt = -z + b·x·y + x·z"
    ),
    description=(
        "The Lorenz84 attractor is a simplified version of the classic Lorenz attractor. "
        "The Lorenz attractor was derived by Edward Lorenz in 1963 to model "
        "atmospheric convection. He derived the Lorenz84 system in 1984 to "
        "model the global scale flow of the atmosphere driven by the "
        "temperature difference between the equator and the poles influenced by "
        "the Earth's rotation."
    ),
)
