# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numba

from ..core.models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _duffing(x_var, t, params, out):
    x, y = x_var
    a, b, c = params

    out[0] = y
    out[1] = -a * y + b * x - c * x**3


_duffing_oscillator = AttractorConfig(
    name="duffing",
    equation=_duffing,
    params=[
        AttractorParam("a", 0.25, 0, 5, 0.01),
        AttractorParam("b", 1.0, 0, 5, 0.01),
        AttractorParam("c", 1.0, 0, 5, 0.01),
    ],
    initial_conditions=[2.0, 0.0],
    time_defaults={"t_min": 0, "t_max": 50, "n": 10000},
    camera_distance=60,
    camera_elevation=20,
    camera_azimuth=-40,
    pan=25,
    equation_text=("dx/dt = y\ndy/dt = -a·y+b·x-c*x³"),
    description=(""),
    variables=("x", "y"),
)
