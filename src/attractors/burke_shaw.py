from typing import Any

from .models import AttractorConfig, AttractorParam


def _burke_shaw(
    x_var: list[Any],
    t: int | float,
    a: int | float,
    b: int | float,
) -> list[int | float]:
    x, y, z = x_var
    dxdt = -a * (x + y)
    dydt = -y - a * x * z
    dzdt = a * x * y + b

    return [dxdt, dydt, dzdt]


_burke_shaw_attractor = AttractorConfig(
    "burke_shaw",
    _burke_shaw,
    params=[
        AttractorParam("$a$", 5.09, 0.0, 30.0, 0.01),
        AttractorParam("$b$", 6.28, 0.0, 100.0, 0.01),
    ],
    initial_conditions=[0.1, 0.1, 0.1],
    time_defaults={"t_min": 0, "t_max": 100, "n": 100000},
    camera_distance=6,
    camera_elevation=10,
    camera_azimuth=50,
    pan=-15,
    equation_text=("dx/dt = -a(x + y)\ndy/dt = -y - a·x·z\ndz/dt = a·x·y + b"),
    description=(
        "The Burke-Shaw attractor is a variant of the Lorenz system. It's highly "
        "symmetrical, being invariant under a 180-degree rotation about the "
        "$z$-axis, which often results in a double wing appearance. It has a "
        "similar algebraic structure to the Lorenz system, but because of it's "
        "higher topological complexity it can take a range of shapes."
    ),
)
