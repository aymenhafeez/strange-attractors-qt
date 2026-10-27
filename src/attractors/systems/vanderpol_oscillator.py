# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numba

from ..core.models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _vanderpol(x_var, t, params, out):
    x, y = x_var
    (a,) = params

    out[0] = y
    out[1] = a * (1 - x**2) * y - x


_vanderpol_oscillator = AttractorConfig(
    name="vanderpol",
    equation=_vanderpol,
    params=[
        AttractorParam("a", 1.5, 0, 5, 0.01),
    ],
    initial_conditions=[2.0, 0.0],
    time_defaults={"t_min": 0, "t_max": 50, "n": 10000},
    camera_distance=60,
    camera_elevation=20,
    camera_azimuth=-40,
    pan=25,
    equation_text=("dx/dt = y\ndy/dt = a·(1 - x²)·y-x"),
    description=(""),
    variables=("x", "y"),
)
