from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class AttractorParam:
    name: str
    default: float
    min_val: float
    max_val: float
    step: float = 0.01


@dataclass
class AttractorConfig:
    name: str
    equation: Callable
    params: list[AttractorParam]
    initial_conditions: list[float]
    time_defaults: dict[str, int]
    camera_distance: int = 70
    camera_elevation: int = 10
    camera_azimuth: int = 10
    pan: int | float = 0
    description: str = ""
    equation_text: str = ""
