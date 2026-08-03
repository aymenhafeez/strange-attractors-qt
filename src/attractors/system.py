from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .jupyter_console_panel import ConsolePlot
from .sections import (
    AXES,
    COORDINATE_COLUMNS,
    axis_index,
    crossing_direction,
    plane_crossings,
    section_axes,
)
from .solution_validation import validate_solutions
from .solver import solve_attractor

]
PLOT_MODE_REPLACE = "replace"
PLOT_MODE_OVERLAY = "overlay"

HELP_ROWS = [
    ("context", "summary()", "Current system, solve size, bounds and camera"),
    ("context", "status()", "Solve freshness and last error state"),
    ("context", "describe()", "System description and equation text"),
    ("context", "parameters()", "Parameter values, defaults and ranges"),
    ("control", "set_parameters(values, solve=False)", "Update main parameters"),
    ("control", "set_time(n=None, t_max=None, solve=False)", "Update main solve time"),
    ("control", "solve()", "Run a full solve for the current main state"),
    ("context", "trajectories()", "Per trajectory length, endpoints and bounds"),
    ("data", "solutions", "Read only trajectory arrays"),
    ("data", "solution(index=0, copy=False)", "One trajectory array"),
    (
        "data",
        "solve_variant(values=None, n=None, t_max=None)",
        "Non mutating solve snapshot for comparison",
    ),
    ("data", "to_dataframe(trajectory=None)", "Trajectory samples as a DataFrame"),
    ("data", "sample(n, trajectory=None)", "Evenly sampled trajectory DataFrame"),
    ("geometry", "bounds()", "Coordinate min and max values"),
    ("geometry", "radius(trajectory=None)", "Distance from origin over time"),
    ("geometry", "speed(trajectory=None)", "Approximate phase space speed"),
    ("geometry", "displacement(trajectory=None)", "Distance from the starting point"),
    ("geometry", "extrema(trajectory=None)", "Local minima and maxima by axis"),
    ("chaos", "separation(a=0, b=1, log=False)", "Distance between trajectories"),
    ("chaos", "separation_summary(a=0, b=1)", "Quick separation statistics"),
    ("chaos", "separation_fit(a=0, b=1)", "Linear fit of log separation"),
    ("recurrence", "nearest_returns()", "Closest lagged sampled returns"),
    ("recurrence", "return_lags()", "Return durations from nearest returns"),
    ("recurrence", "return_lag_summary()", "Quick return duration statistics"),
    (
        "sections",
        "crossings(axis='z', value=None, t_max=None)",
        "Interpolated plane crossings",
    ),
    ("plotting", "plot_xy() / plot_xz() / plot_yz()", "Phase projection plots"),
    ("plotting", "plot_axis(axis, live=False)", "Coordinate over time"),
    (
        "plotting",
        "plot_radius(live=False) / plot_speed(live=False)",
        "Geometry time series plots",
    ),
    ("plotting", "plot_displacement(live=False)", "Displacement over time"),
    ("plotting", "plot_separation(live=False)", "Trajectory separation over time"),
    ("plotting", "plot_separation_fit(live=False)", "Log separation with fitted line"),
    ("plotting", "plot_crossings()", "Plane crossings as a 2D section"),
    (
        "plotting",
        "plot_vector_field(live=False)",
        "Vector field on a 2D phase space slice",
    ),
    ("plotting", "plot_returns() / plot_return_lags()", "Recurrence plots"),
    (
        "live",
        "plot_axis(axis, live=True, mode='replace')",
        "Keep an axis time series plot linked to main",
    ),
    (
        "live",
        "plot_radius(live=True) / plot_speed(live=True)",
        "Keep geometry time series plots linked to main",
    ),
    (
        "live",
        "plot_projection(x_axis, y_axis, live=True, mode='replace')",
        "Keep a phase plot linked to main",
    ),
    (
        "live",
        "plot_separation(a=0, b=1, live=True, mode='replace')",
        "Keep separation linked to main",
    ),
    (
        "live",
        "plot_separation_fit(a=0, b=1, live=True, mode='replace')",
        "Keep log separation and fit linked to main",
    ),
    (
        "live",
        "plot_vector_field(x_axis='x', y_axis='y', live=True)",
        "Keep a vector field slice linked to main parameters",
    ),
    ("live", "live_plots()", "List plots linked to the main solution"),
    ("live", "unfollow(plot=None)", "Stop one live plot from following main"),
    ("live", "unfollow_all()", "Stop all live plots from following main"),
]
EXAMPLE_ROWS = [
    (
        "Inspect current system",
        "system.summary(); system.parameters(); system.trajectories()",
    ),
    ("Plot a phase projection", "system.plot_xz()"),
    ("Plot a coordinate over time", "system.plot_axis('z')"),
    ("Set a parameter and solve", "system.set_parameters({'rho': 32}, solve=True)"),
    ("Extend solve time", "system.set_time(t_max=120, solve=True)"),
    (
        "Compare a parameter variant",
        "variant = system.solve_variant({'rho': 32}, n=50000); variant.plot_xz()",
    ),
    (
        "Compare nearby trajectories",
        "system.separation_summary(0, 1); system.plot_separation_fit(0, 1)",
    ),
    (
        "Overlay separation fits",
        (
            "system.plot_separation_fit(0, 1, pen='c'); "
            "system.plot_separation_fit(0, 2, pen='y', mode='overlay')"
        ),
    ),
    (
        "Find recurrent states",
        "system.return_lag_summary(); system.nearest_returns(count=50)",
    ),
    ("Plot return durations", "system.plot_return_lags(count=100)"),
    ("Live z while sliders move", "system.plot_axis('z', live=True)"),
    (
        "Overlay coordinates",
        (
            "system.plot_axis('x', live=True, plot='coords', pen='r', label='x'); "
            "system.plot_axis("
            "'y', live=True, plot='coords', mode='overlay', pen='g', label='y'"
            "); "
            "system.plot_axis("
            "'z', live=True, plot='coords', mode='overlay', pen='b', label='z'"
            ")"
        ),
    ),
    ("Live x-z projection", "system.plot_projection('x', 'z', live=True)"),
    ("Live separation fit", "system.plot_separation_fit(0, 1, live=True, plot='sep')"),
    (
        "Live vector field slice",
        (
            "system.plot_vector_field("
            "'x', 'y', live=True, fixed_axis='z', fixed_value=0, plot='field'"
            ")"
        ),
    ),
    ("Review live plots", "system.live_plots()"),
    (
        "Make a section plot",
        "system.plot_crossings('z', value=25, t_max=500, n=100000)",
    ),
    ("Export manageable data", "df = system.sample(2000)"),
]


def _solver_sample_times(t_min, t_max, length):
    if length <= 0:
        return np.array([], dtype=np.float64)

    dt = (t_max - t_min) / length
    return t_min + (np.arange(length, dtype=np.float64) + 1.0) * dt


def _inspectable_config(config):
    if config is None:
        return None

    return replace(
        config,
        params=[replace(param) for param in config.params],
        initial_conditions=list(config.initial_conditions),
    )


def _normalise_initial_conditions(initial_conditions):
    if initial_conditions is None:
        return None

    if isinstance(initial_conditions, np.ndarray):
        array = np.asarray(initial_conditions, dtype=np.float64)
        if array.ndim == 1:
            if array.shape[0] != 3:
                raise ValueError("Initial conditions must contain three coordinates")
            return [array.tolist()]
        if array.ndim == 2 and array.shape[1] == 3:
            return array.tolist()
        raise ValueError("Initial conditions must have shape (3,) or (n, 3)")

    try:
        rows = list(initial_conditions)
    except TypeError as exc:
        raise ValueError("Initial conditions must contain three coordinates") from exc

    if len(rows) == 3 and all(np.isscalar(value) for value in rows):
        return [[float(value) for value in rows]]

    normalised = []
    for row in rows:
        try:
            coords = [float(value) for value in row]
        except TypeError as exc:
            raise ValueError(
                "Initial conditions must contain three coordinates"
            ) from exc
        if len(coords) != 3:
            raise ValueError("Initial conditions must contain three coordinates")
        normalised.append(coords)

    if not normalised:
        raise ValueError("At least one initial condition is required")

    return normalised


class _SnapshotScene:
    """Give the scene state of the current system"""

    def __init__(self, solutions, camera, plot):
        self.trajectory_renderer = SimpleNamespace(
            solutions=tuple(np.asarray(solution) for solution in solutions),
        )
        self.camera_controller = SimpleNamespace(
            get_camera_state=lambda: dict(camera or {}),
        )
        self._plot = plot


class _SnapshotTrajectoryPanel:
    """Give the initial conditions of the current system"""

    def __init__(self, initial_conditions):
        self._initial_conditions = _copy_initial_conditions(initial_conditions)

    def get_trajectories(self):
        return [{"ic": list(ic)} for ic in self._initial_conditions]


class LivePlotHandle:
    def __init__(self, window, plot_name, trace_index):
        self._window = window
        self.plot_name = str(plot_name)
        self.trace_index = int(trace_index)

    def __repr__(self):
        return f"LivePlotHandle(plot={self.plot_name!r}, trace={self.trace_index!r})"

    def __getitem__(self, key):
        return self.spec[key]

    def get(self, key, default=None):
        return self.spec.get(key, default)

    @property
    def spec(self):
        return self._window._live_plots[self.plot_name][self.trace_index]

    @property
    def item(self):
        items = self._window.live_plot_controller.live_items
        return items.get((self.plot_name, self.trace_index))

    @property
    def items(self):
        item = self.item

        if item is None:
            return ()
        if isinstance(item, tuple):
            return item

        return (item,)

    def options(self):
        return pd.Series(dict(self.spec))

    def setPen(self, pen):
        self.spec["pen"] = pen
        for item in self.items:
            item.setPen(pen)

        return self

    def setVisible(self, visible):
        for item in self.items:
            item.setVisible(bool(visible))

        return self

    def setAlpha(self, alpha, auto=False):
        for item in self.items:
            item.setAlpha(float(alpha), auto=auto)

        return self

    def unfollow(self):
        return self._window.live_plot_controller._remove_live_trace(
            self.plot_name,
            self.trace_index,
        )


class _SnapshotWindow:
    """
    Give window state and methods to SystemInspector, keep the data read only separate from the live view
    """

    def __init__(
        self,
        *,
        name,
        config,
        values,
        n,
        t_max,
        initial_conditions,
        solutions,
        camera,
        plot,
        status,
    ):
        self.current_name = name
        self.current_n = int(n)
        self.current_t_max = float(t_max)
        self._config = config
        self._values = dict(values)
        self._solve_state = dict(status)
        self.scene = _SnapshotScene(solutions, camera, plot)
        self.controls = SimpleNamespace(
            trajectory_panel=_SnapshotTrajectoryPanel(initial_conditions),
        )
        self.jupyter_console_panel = SimpleNamespace(plot=plot)

    def _get_current_config_and_values(self):
        return self._config, dict(self._values)

    def _set_console_parameters(self, values, *, solve=False):
        raise RuntimeError("Snapshot parameters are read-only")

    def _set_console_time(self, *, n=None, t_max=None, solve=False):
        raise RuntimeError("Snapshot solve time is read-only")

    def _solve_from_console(self):
        raise RuntimeError("Snapshot solves are read-only")


class SystemInspector:
    def __init__(self, window):
        self._window = window

    def __repr__(self):
        return (
            f"SystemInspector(name={self.name!r}, "
            f"trajectories={len(self.solutions)}, n={self.n}, t_max={self.t_max})"
        )

    @property
    def name(self):
        return self._window.current_name

    @property
    def config(self):
        config, _values = self._window._get_current_config_and_values()

        return _inspectable_config(config)

    @property
    def values(self):
        _config, values = self._window._get_current_config_and_values()
        return dict(values)

    @property
    def n(self):
        return int(self._window.current_n)

    @property
    def t_max(self):
        return self._window.current_t_max

    @property
    def t_min(self):
        config = self.config
        if config is None:
            return 0
        return config.time_defaults.t_min

    @property
    def camera(self):
        return self._window.scene.camera_controller.get_camera_state()

    @property
    def solutions(self):
        solutions = self._window.scene.trajectory_renderer.solutions or []
        views = []
        for solution in solutions:
            # make the view read only so it can't accidentally get modified
            view = np.asarray(solution).view()
            view.setflags(write=False)
            views.append(view)

        return tuple(views)

    @property
    def has_solutions(self):
        return bool(self._window.scene.trajectory_renderer.solutions)

    def help(self):
        return pd.DataFrame(HELP_ROWS, columns=["category", "method", "description"])

    def examples(self):
        return pd.DataFrame(EXAMPLE_ROWS, columns=["task", "commands"])

    def summary(self):
        bounds = self.bounds()
        result = {
            "name": self.name,
            "parameters": len(self.values),
            "trajectories": len(self.solutions),
            "has_solutions": self.has_solutions,
            "n": self.n,
            "t_min": self.t_min,
            "t_max": self.t_max,
            "camera": self.camera,
        }
        for axis in COORDINATE_COLUMNS:
            result[f"{axis}_min"] = (
                None if axis not in bounds.index else bounds.loc[axis, "min"]
            )
            result[f"{axis}_max"] = (
                None if axis not in bounds.index else bounds.loc[axis, "max"]
            )
        return pd.Series(result)

    def status(self):
        state = dict(self._window._solve_state)
        result = {
            "solving": bool(state.get("solving", False)),
            "valid": bool(state.get("valid", self.has_solutions)),
            "stale": bool(state.get("stale", False)),
            "partial": bool(state.get("partial", False)),
            "last_error": state.get("last_error"),
            "request_id": state.get("request_id"),
            "attractor": state.get("attractor", self.name),
            "parameters": dict(state.get("parameters", self.values)),
            "n": state.get("n", self.n),
            "t_max": state.get("t_max", self.t_max),
            "trajectories": state.get("trajectories", len(self.solutions)),
            "solution_points": list(
                state.get(
                    "solution_points",
                    [len(solution) for solution in self.solutions],
                )
            ),
            "console_solution_count": len(self.solutions),
        }
        return pd.Series(result)

    def describe(self):
        config = self.config
        if config is None:
            return pd.Series({"name": self.name, "description": ""})

        return pd.Series(
            {
                "name": self.name,
                "config_name": config.name,
                "description": config.description,
                "equation": config.equation_text,
            }
        )

    def parameters(self):
        config = self.config
        if config is None:
            return pd.DataFrame(
                columns=["value", "default", "min", "max", "step"],
                index=pd.Index([], name="name"),
            )

        rows = []
        values = self.values
        for param in config.params:
            rows.append(
                {
                    "name": param.name,
                    "value": values.get(param.name),
                    "default": param.default,
                    "min": param.min_val,
                    "max": param.max_val,
                    "step": param.step,
                }
            )
        if not rows:
            return pd.DataFrame(
                columns=["value", "default", "min", "max", "step"],
                index=pd.Index([], name="name"),
            )

        return pd.DataFrame(rows).set_index("name")

    # these three are controls for updating the main viewport plot from the console
    def set_parameters(self, values, *, solve=False):
        return self._window._set_console_parameters(dict(values), solve=solve)

    def set_time(self, *, n=None, t_max=None, solve=False):
        return self._window._set_console_time(n=n, t_max=t_max, solve=solve)

    def solve(self):
        return self._window._solve_from_console()

    def trajectories(self):
        """Inspect plotted trajectories"""
        rows = []
        initial_conditions = self._initial_conditions()
        metadata = self._trajectory_metadata()
        for i, solution in enumerate(self.solutions):
            finite = solution[np.isfinite(solution).all(axis=1)]
            trajectory_meta = metadata[i] if i < len(metadata) else {}
            row = {
                "trajectory": i,
                "label": trajectory_meta.get("label", f"T{i}"),
                "colour": trajectory_meta.get("colour"),
                "alpha": trajectory_meta.get("alpha"),
                "render_mode": trajectory_meta.get("render_mode"),
                "n": trajectory_meta.get("n", self._trajectory_solve_spec(i).get("n")),
                "t_max": trajectory_meta.get(
                    "t_max",
                    self._trajectory_solve_spec(i).get("t_max"),
                ),
                "length": len(solution),
                "initial_x": self._coordinate(initial_conditions, i, 0),
                "initial_y": self._coordinate(initial_conditions, i, 1),
                "initial_z": self._coordinate(initial_conditions, i, 2),
                "final_x": solution[-1, 0] if len(solution) else None,
                "final_y": solution[-1, 1] if len(solution) else None,
                "final_z": solution[-1, 2] if len(solution) else None,
            }
            for axis, col in AXES.items():
                row[f"{axis}_min"] = finite[:, col].min() if len(finite) else None
                row[f"{axis}_max"] = finite[:, col].max() if len(finite) else None
            rows.append(row)

        if not rows:
            return pd.DataFrame(columns=self._trajectory_columns()).set_index(
                "trajectory"
            )

        return pd.DataFrame(rows).set_index("trajectory")

    def solution(self, index=0, *, copy=False):
        solutions = self.solutions
        try:
            solution = solutions[index]
        except IndexError as exc:
            raise IndexError(f"No trajectory at index {index}") from exc
        if copy:
            return solution.copy()

        return solution

    def solve_variant(
        self,
        values=None,
        *,
        n=None,
        t_max=None,
        initial_conditions=None,
    ):
        config = self.config
        if config is None:
            raise ValueError("No attractor selected")

        variant_values = self._variant_values(values)
        solve_n = self._positive_int(self.n if n is None else n, "n")
        solve_t_max = self.t_max if t_max is None else float(t_max)
        if solve_t_max <= self.t_min:
            raise ValueError("t_max must be greater than t_min")

        solve_ics = _normalise_initial_conditions(initial_conditions)
        if solve_ics is None:
            solve_ics = _copy_initial_conditions(self._initial_conditions())
        if not solve_ics:
            raise ValueError("At least one initial condition is required")

        solutions = [
            solve_attractor(
                config,
                variant_values,
                solve_n,
                t_max=solve_t_max,
                ic=ic,
            )
            for ic in solve_ics
        ]
        is_valid, message = validate_solutions(solutions)
        if not is_valid:
            raise ValueError(message)

        status = {
            "solving": False,
            "valid": True,
            "stale": False,
            "partial": False,
            "last_error": None,
            "request_id": None,
            "attractor": self.name,
            "parameters": dict(variant_values),
            "n": solve_n,
            "t_max": solve_t_max,
            "trajectories": len(solutions),
            "solution_points": [len(solution) for solution in solutions],
        }
        return SystemInspector(
            _SnapshotWindow(
                name=f"{self.name} variant",
                config=config,
                values=variant_values,
                n=solve_n,
                t_max=solve_t_max,
                initial_conditions=solve_ics,
                solutions=solutions,
                camera=self.camera,
                plot=self._plot_target(None),
                status=status,
            )
        )

    def time(self, index=0):
        solution = self.solution(index)
        spec = self._trajectory_solve_spec(index)

        return _solver_sample_times(
            self.t_min,
            spec.get("t_max", self.t_max),
            len(solution),
        )

    def bounds(self):
        solutions = self.solutions
        if not solutions:
            return pd.DataFrame(columns=["min", "max"], index=COORDINATE_COLUMNS)

        points = np.concatenate(solutions, axis=0)
        finite = points[np.isfinite(points).all(axis=1)]

        if len(finite) == 0:
            return pd.DataFrame(columns=["min", "max"], index=COORDINATE_COLUMNS)

        return pd.DataFrame(
            {"min": finite.min(axis=0), "max": finite.max(axis=0)},
            index=COORDINATE_COLUMNS,
        )

    def to_dataframe(self, trajectory=None):
        rows = []
        solutions = self.solutions
        selected = range(len(solutions)) if trajectory is None else [trajectory]

        for i in selected:
            solution = self.solution(i)
            frame = pd.DataFrame(solution, columns=COORDINATE_COLUMNS)
            frame.insert(0, "t", self.time(i))
            frame.insert(0, "step", np.arange(len(solution)))
            frame.insert(0, "trajectory", i)
            rows.append(frame)

        if not rows:
            return pd.DataFrame(
                columns=["trajectory", "step", "t", *COORDINATE_COLUMNS]
            )

        return pd.concat(rows, ignore_index=True)

    def sample(self, n, trajectory=None):
        try:
            sample_size = int(n)
        except (TypeError, ValueError) as exc:
            raise ValueError("Sample size must be a positive integer") from exc
        if sample_size <= 0:
            raise ValueError("Sample size must be a positive integer")

        rows = []
        solutions = self.solutions
        selected = range(len(solutions)) if trajectory is None else [trajectory]
        for i in selected:
            solution = self.solution(i)
            indices = self._sample_indices(len(solution), sample_size)
            frame = pd.DataFrame(solution[indices].copy(), columns=COORDINATE_COLUMNS)
            times = self.time(i)
            frame.insert(0, "t", times[indices])
            frame.insert(0, "step", indices)
            frame.insert(0, "trajectory", i)
            rows.append(frame)

        if not rows:
            return pd.DataFrame(
                columns=["trajectory", "step", "t", *COORDINATE_COLUMNS]
            )

        return pd.concat(rows, ignore_index=True)

    def plot_projection(
        self,
        x_axis="x",
        y_axis="y",
        *,
        trajectory=0,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
    ):
        x_name = str(x_axis).lower()
        y_name = str(y_axis).lower()
        x_col = axis_index(x_name)
        y_col = axis_index(y_name)
        plot_mode = self._plot_mode(mode)
        if live:
            return self._follow_live_plot(
                "projection",
                plot=plot,
                mode=plot_mode,
                x_axis=x_name,
                y_axis=y_name,
                trajectory=int(trajectory),
                pen=pen,
                label=label,
            )

        solution = self.solution(trajectory)
        plot_kwargs = {}
        if pen is not None:
            plot_kwargs["pen"] = pen
        if label is not None:
            plot_kwargs["name"] = str(label)
        return self._plot_line(
            self._plot_target(plot),
            solution[:, x_col],
            solution[:, y_col],
            mode=plot_mode,
            bottom=x_name,
            left=y_name,
            **plot_kwargs,
        )

    def plot_xy(self, **kwargs):
        return self.plot_projection("x", "y", **kwargs)

    def plot_xz(self, **kwargs):
        return self.plot_projection("x", "z", **kwargs)

    def plot_yz(self, **kwargs):
        return self.plot_projection("y", "z", **kwargs)

    def plot_axis(
        self,
        axis,
        *,
        trajectory=0,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        axis_name = str(axis).lower()
        axis_col = axis_index(axis_name)
        plot_mode = self._plot_mode(mode)
        if live:
            return self._follow_live_plot(
                "axis",
                plot=plot,
                mode=plot_mode,
                axis=axis_name,
                trajectory=int(trajectory),
                pen=pen,
                label=label,
                zoom_region=zoom_region,
            )

        solution = self.solution(trajectory)
        return self._plot_timeseries(
            self.time(trajectory),
            solution[:, axis_col],
            axis_name,
            plot=plot,
            mode=plot_mode,
            pen=pen,
            label=label,
            zoom_region=zoom_region,
        )

        try:
            return AXES[str(axis).lower()]
        except KeyError as exc:
            raise ValueError("Axis must be one of x, y or z") from exc
    def plot_crossings(
        self,
        axis="z",
        value=None,
        *,
        x_axis=None,
        y_axis=None,
        direction="both",
        trajectory=None,
        t_max=None,
        n=None,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        symbol="+",
        symbolSize=None,
    ):
        frame = self.crossings(
            axis,
            value,
            direction=direction,
            trajectory=trajectory,
            t_max=t_max,
            n=n,
        )
        section_x, section_y = section_axes(axis)
        x_name = section_x if x_axis is None else str(x_axis).lower()
        y_name = section_y if y_axis is None else str(y_axis).lower()
        axis_index(x_name)
        axis_index(y_name)
        plot_kwargs = {"pen": pen, "symbol": symbol}
        if symbolSize is not None:
            plot_kwargs["symbolSize"] = symbolSize
        return self._plot_scatter(
            self._plot_target(plot),
            frame[x_name].to_numpy(),
            frame[y_name].to_numpy(),
            mode=self._plot_mode(mode),
            bottom=x_name,
            left=y_name,
            **plot_kwargs,
        )

