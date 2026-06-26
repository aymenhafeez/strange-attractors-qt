from typing import Any

import numba

from .models import AttractorConfig, AttractorParam


@numba.njit
def loop_chaotic(
    x_var: list[Any],
    t: int | float,
    a: int | float,
    b: int | float,
) -> list[int | float]:
    x, y, z = x_var
    dxdt = y * b
    dydt = -x - y * z
    dzdt = y**2 - a

    return [dxdt, dydt, dzdt]


_loop_chaotic_attractor = AttractorConfig(
    "loop_chaotic",
    loop_chaotic,
    params=[
        AttractorParam("a", 1.0, 0.0, 20.0, 0.01),
        AttractorParam("b", 1.796, 0.0, 10.0, 0.01),
    ],
    initial_conditions=[-0.1, -1, 0.3],
    time_defaults={"t_min": 0, "t_max": 750, "n": 100000},
    camera_distance=7,
    camera_elevation=10,
    camera_azimuth=50,
    pan=0.5,
    equation_text=("dx/dt = b·y\ndy/dt = -x - y·z\ndz/dt = y² - a"),
    description=(
        "This is a variant of the Nosé-Hoover attractor, which was designed to "
        "simulate fixed temperature molecular dynamics. It can take a wide "
        "variety of unique shapes with some trajectories looking seemingly "
        "random and chaotic from certain angles, but well formed and "
        "deterministic from others."
    ),
)
