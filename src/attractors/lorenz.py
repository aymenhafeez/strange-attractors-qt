from typing import Any

import numba

from .models import AttractorConfig, AttractorParam


@numba.njit
def lorenz(
    x_var: list[Any],
    t: int | float,
    a: int | float,
    b: int | float,
    c: int | float,
) -> list[int | float]:
    x, y, z = x_var

    dx_dt = a * (y - x)
    dy_dt = x * (b - z) - y
    dz_dt = x * y - c * z

    return [dx_dt, dy_dt, dz_dt]


_lorenz_attractor = AttractorConfig(
    name="lorenz",
    equation=lorenz,
    params=[
        AttractorParam("a", 10.0, 0, 50, 0.001),
        AttractorParam("b", 28.0, 0, 150, 0.001),
        AttractorParam("c", 8 / 7, 0, 10, 0.001),
    ],
    initial_conditions=[0.0, 1.5, 15.0],
    time_defaults={"t_min": 0, "t_max": 50, "n": 100000},
    camera_distance=50,
    camera_elevation=20,
    camera_azimuth=10,
    pan=25,
    equation_text=("dx/dt = a(y - x)\ndy/dt = x(b - z) - y\ndz/dt = xy - cz"),
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
