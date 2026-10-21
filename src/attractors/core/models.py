# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass
class AttractorParam:
    name: str
    default: float
    min_val: float
    max_val: float
    step: float = 0.01


@dataclass(frozen=True)
class TimeDefaults(Mapping):
    t_min: int | float
    t_max: int | float
    n: int

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                t_min=value["t_min"],
                t_max=value["t_max"],
                n=int(value["n"]),
            )
        raise TypeError("time_defaults must be a mapping or TimeDefaults")

    def as_dict(self):
        return {"t_min": self.t_min, "t_max": self.t_max, "n": self.n}

    def __getitem__(self, key):
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self):
        return 3

    def __eq__(self, other):
        if isinstance(other, Mapping):
            return self.as_dict() == dict(other)
        return super().__eq__(other)


@dataclass
class AttractorConfig:
    name: str
    equation: Callable
    params: list[AttractorParam]
    initial_conditions: list[float]
    time_defaults: TimeDefaults | Mapping[str, int | float]
    camera_distance: int = 70
    camera_elevation: int = 10
    camera_azimuth: int = 10
    pan: int | float = 0
    description: str = ""
    equation_text: str = ""
    variables: tuple[str, ...] = ("x", "y", "z")

    def __post_init__(self):
        self.time_defaults = TimeDefaults.from_value(self.time_defaults)

        if self.variables not in (
            ("x", "y"),
            ("x", "y", "z"),
        ):
            raise ValueError("variables must be either ('x', 'y') or ('x', 'y', 'z')")

        if len(self.initial_conditions) != self.dimension:
            raise ValueError(
                "initial_conditions must have the same length as variables"
            )

    @property
    def dimension(self):
        return len(self.variables)
