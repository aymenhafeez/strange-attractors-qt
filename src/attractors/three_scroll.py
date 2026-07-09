import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _three_scroll(x_var, t, params):
    x, y, z = x_var
    a, b, c, d, e, f = params
    dxdt = a * (y - x) + d * x * z
    dydt = b * x - x * z + f * y
    dzdt = c * z + x * y - e * x**2

    return np.array([dxdt, dydt, dzdt])


_three_scroll_attractor = AttractorConfig(
    "three_scroll",
    _three_scroll,
    params=[
        AttractorParam("$a$", 32.48, 0.0, 50.0, 0.01),
        AttractorParam("$b$", 71.00, 40.0, 100.0, 0.01),
        AttractorParam("$c$", 1.18, 0.0, 5.0, 0.01),
        AttractorParam("$d$", 0.13, 0.0, 1.0, 0.001),
        AttractorParam("$e$", 0.57, 0.47, 2.0, 0.001),
        AttractorParam("$f$", 14.7, 5.0, 30.0, 0.01),
    ],
    initial_conditions=[-0.29, -0.25, -0.59],
    time_defaults={"t_min": 0, "t_max": 30, "n": 100000},
    camera_distance=300,
    camera_elevation=20,
    camera_azimuth=50,
    pan=100,
    equation_text=(
        "dx/dt = a(y - x) + d·x·z\ndy/dt = b·x - x·z + f·y\ndz/dt = c·z + x·y - e·x²"
    ),
    description=(
        "The three scroll chaotic attractor is a 3D quadratic system that extends the "
        "classical two wing Lorenz model by adding a third stable focal point. It "
        "consists of two symmetry related scrolls flanking the $z$ axis and a "
        "unique third scroll that rotates directly around it. This system is "
        "frequently studied in nonlinear dynamics and secure communications due to "
        "its high sensitivity to initial conditions and its complex, non-integer "
        "fractal dimension."
    ),
)
