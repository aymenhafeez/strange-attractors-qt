# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass

import numpy as np

AXES = {"x": 0, "y": 1, "z": 2}
COORDINATE_COLUMNS = ["x", "y", "z"]


@dataclass(frozen=True)
class PlaneCrossings:
    axis: str
    level: float
    steps: np.ndarray
    times: np.ndarray
    points: np.ndarray
    directions: np.ndarray

    def section_coordinates(self):
        variables = COORDINATE_COLUMNS[: self.points.shape[1]]
        axes = section_axes(self.axis, variables)

        return tuple(self.points[:, AXES[name]] for name in axes)


def axis_index(axis):
    try:
        return AXES[str(axis).lower()]
    except KeyError as exc:
        raise ValueError("Axis must be one of x, y or z") from exc


def crossing_direction(direction):
    normalised = str(direction).lower()
    if normalised not in {"both", "positive", "negative"}:
        raise ValueError("Direction must be one of both, positive or negative")
    return normalised


def section_axes(axis, variables=("x", "y", "z")):
    axis_name = str(axis).lower()
    axis_index(axis_name)

    if axis_name not in variables:
        raise ValueError(f"Coordinate {axis_name} is not available")

    return tuple(name for name in variables if name != axis_name)


def plane_crossings(solution, axis, value, *, direction="both", times=None):
    axis_name = str(axis).lower()
    axis_col = axis_index(axis_name)
    level = float(value)
    direction = crossing_direction(direction)
    solution = np.asarray(solution)

    if solution.ndim != 2 or solution.shape[1] not in (2, 3):
        raise ValueError("Solution must be an array with x, y and z columns")

    dimension = solution.shape[1]

    if times is None:
        times = np.arange(len(solution), dtype=np.float64)
    else:
        times = np.asarray(times, dtype=np.float64)
        if len(times) != len(solution):
            raise ValueError("Times must have the same length as the solution")

    empty = PlaneCrossings(
        axis=axis_name,
        level=level,
        steps=np.array([], dtype=np.int64),
        times=np.array([], dtype=np.float64),
        points=np.empty((0, dimension)),
        directions=np.array([]),
    )
    if len(solution) < 2:
        return empty

    series = solution[:, axis_col] - level
    finite = (
        np.isfinite(series[:-1])
        & np.isfinite(series[1:])
        & np.isfinite(times[:-1])
        & np.isfinite(times[1:])
        & np.isfinite(solution[:-1, :dimension]).all(axis=1)
        & np.isfinite(solution[1:, :dimension]).all(axis=1)
    )
    rising = (series[:-1] < 0) & (series[1:] >= 0)
    falling = (series[:-1] > 0) & (series[1:] <= 0)
    if direction == "positive":
        mask = rising
    elif direction == "negative":
        mask = falling
    else:
        mask = rising | falling

    steps = np.flatnonzero(mask & finite)
    if len(steps) == 0:
        return empty

    delta = series[steps + 1] - series[steps]
    valid = delta != 0
    steps = steps[valid]
    delta = delta[valid]
    if len(steps) == 0:
        return empty

    frac = -series[steps] / delta
    points = solution[steps, :dimension] + frac[:, None] * (
        solution[steps + 1, :dimension] - solution[steps, :dimension]
    )
    crossing_times = times[steps] + frac * (times[steps + 1] - times[steps])
    directions = np.where(series[steps + 1] > series[steps], "positive", "negative")

    return PlaneCrossings(
        axis=axis_name,
        level=level,
        steps=steps.astype(np.int64, copy=False),
        times=crossing_times.astype(np.float64, copy=False),
        points=points.astype(np.float64, copy=False),
        directions=directions.astype(object, copy=False),
    )
