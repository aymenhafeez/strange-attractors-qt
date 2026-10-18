# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from .app import Window
from .core.solver import solve_attractor
from .systems.registry import ATTRACTORS

__all__ = ["ATTRACTORS", "Window", "solve_attractor"]
