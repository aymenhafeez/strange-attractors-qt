from .app import Window
from .core.solver import solve_attractor
from .systems.registry import ATTRACTORS

__all__ = ["ATTRACTORS", "Window", "solve_attractor"]
