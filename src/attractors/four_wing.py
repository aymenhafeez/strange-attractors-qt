import numba
import numpy as np

from .models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _four_wing(x_var, t, params):
    x, y, z = x_var
    a, b, c = params

    dx_dt = a * x + y * z
    dy_dt = b * x + c * y - x * z
    dz_dt = -z - x * y

    return np.array([dx_dt, dy_dt, dz_dt])


_four_wing_attractor = AttractorConfig(
    name="Four wing",
    equation=_four_wing,
    params=[
        AttractorParam("a", 0.2, 0.0, 0.5, 0.01),
        AttractorParam("b", 0.01, -0.5, 0.5, 0.01),
        AttractorParam("c", -0.4, -0.6, 0.0, 0.01),
    ],
    initial_conditions=[1.3, -0.18, 0.01],
    time_defaults={"t_min": 0, "t_max": 500, "n": 100000},
    camera_distance=7,
    camera_elevation=15,
    camera_azimuth=-40,
    pan=0,
    equation_text=("dx/dt = a·x + y·z\ndy/dt = b·x + c·y - x*z\ndz/dt = -z - x·y"),
    description=(
        "The four wing attractor is a set of chaotic solutions to a 3D system of "
        "equations that builds on classic Lorenz dynamics. It is famous for its "
        "distinct four lobed shape, where trajectories loop endlessly around four "
        "symmetric wings without ever repeating or crossing. This system is a prime "
        "example of chaos, showing how tiny changes in parameters cause trajectories "
        "to unpredictably transition between the wings."
    ),
)
