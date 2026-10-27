# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from .aizawa import _aizawa_attractor
from .burke_shaw import _burke_shaw_attractor
from .dadras import _dadras_attractor
from .double_scroll import _double_scroll_attractor
from .duffing_oscillator import _duffing_oscillator
from .forced_duffing_oscillator import _forced_duffing_oscillator
from .four_wing import _four_wing_attractor
from .loop_chaotic import _loop_chaotic_attractor
from .lorenz import _lorenz_attractor
from .lorenz84 import _lorenz84_attractor
from .three_scroll import _three_scroll_attractor
from .vanderpol_oscillator import _vanderpol_oscillator

ATTRACTORS = {
    "Lorenz": _lorenz_attractor,
    "Three-scroll": _three_scroll_attractor,
    "Double-scroll": _double_scroll_attractor,
    "Lorenz84": _lorenz84_attractor,
    "Aizawa": _aizawa_attractor,
    "Loop chaotic": _loop_chaotic_attractor,
    "Burke-Shaw": _burke_shaw_attractor,
    "Dadras": _dadras_attractor,
    "Four wing": _four_wing_attractor,
    "Duffing oscillator": _duffing_oscillator,
    "Forced Duffing oscillator": _forced_duffing_oscillator,
    "Van der Pol oscillator": _vanderpol_oscillator,
}
