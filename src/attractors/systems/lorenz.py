import numba
import numpy as np

from ..core.models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _lorenz(x_var, t, params, out):
    x, y, z = x_var
    a, b, c = params

    out[0] = a * (y - x)
    out[1] = x * (b - z) - y
    out[2] = x * y - c * z


_lorenz_attractor = AttractorConfig(
    name="lorenz",
    equation=_lorenz,
    params=[
        AttractorParam("a", 10.0, 0, 50, 0.01),
        AttractorParam("b", 28.0, 0, 150, 0.01),
        AttractorParam("c", 8 / 3, 0, 10, 0.01),
    ],
    initial_conditions=[0.0, 1.5, 15.0],
    time_defaults={"t_min": 0, "t_max": 50, "n": 100000},
    camera_distance=60,
    camera_elevation=20,
    camera_azimuth=-40,
    pan=25,
    equation_text=("dx/dt = a(y - x)\ndy/dt = x(b - z) - y\ndz/dt = x·y - c·z"),
    description=(
        "The Lorenz attractor is a set of chaotic solutions to a 3D system of "
        "equations modelling simplified atmospheric convection. It is famous "
        "for its 'butterfly' shape, where trajectories loop infinitely around "
        "two symmetric wings without ever repeating or intersecting. The Lorenz "
        "attractor is the classic example of a chaotic system used to "
        "demonstrate how small changes in model parameters can lead to "
        "drastically different trajectories."
    ),
)
