# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np


def separation(sol_a, times_a, sol_b, times_b):
    length = min(len(times_a), len(times_b))
    times = times_a[:length]
    if not np.allclose(times, times_b[:length], rtol=1e-9, atol=1e-12):
        raise ValueError(
            f"Sample times differ: {len(times_a)} samples to t={times_a[-1]:g} "
            f"and {len(times_b)} samples to t={times_b[-1]:g}"
        )

    return times, np.linalg.norm(sol_a[:length] - sol_b[:length], axis=1)
