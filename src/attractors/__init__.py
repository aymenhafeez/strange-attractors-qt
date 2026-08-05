from .app import Window
from .solver import solve_attractor
from .systems.registry import ATTRACTORS

__all__ = ["ATTRACTORS", "Window", "solve_attractor"]
