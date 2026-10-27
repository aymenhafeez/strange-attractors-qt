# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numba
import numpy as np

from ..core.models import AttractorConfig, AttractorParam


@numba.njit(nogil=True)
def _forced_duffing(x_var, t, params, out):
    x, y = x_var
    a, b = params

    out[0] = y
    out[1] = -a * y + x - x**3 + b * np.cos(t)


_forced_duffing_oscillator = AttractorConfig(
    name="forced duffing",
    equation=_forced_duffing,
    params=[
        AttractorParam("a", 0.2, 0.05, 0.5, 0.01),
        AttractorParam("b", 0.3, 0.1, 0.5, 0.001),
    ],
    initial_conditions=[1.0, 0.0],
    time_defaults={"t_min": 0, "t_max": 50, "n": 10000},
    camera_distance=60,
    camera_elevation=20,
    camera_azimuth=-40,
    pan=25,
    equation_text=("dx/dt = y\ndy/dt = -a·y + x - x³ + b·cos(t)"),
    description=(""),
    variables=("x", "y"),
)
