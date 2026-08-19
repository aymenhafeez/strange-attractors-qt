from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd

from ..core.sections import (
    AXES,
    COORDINATE_COLUMNS,
    axis_index,
    crossing_direction,
    plane_crossings,
    section_axes,
)
from ..core.solution_validation import validate_solutions
from ..core.solver import solve_attractor
from .jupyter_console_panel import ConsolePlot

VECTOR_FIELD_SPEED_PENS = [
    (65, 105, 155),
    (55, 135, 175),
    (60, 165, 165),
    (120, 185, 115),
    (235, 190, 80),
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
    ("chaos", "separation(a=0, b=1, log=False)", "Distance between trajectories"),
    ("chaos", "separation_summary(a=0, b=1)", "Quick separation statistics"),
    ("chaos", "separation_fit(a=0, b=1)", "Linear fit of log separation"),
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
    ("live", "unfollow(plot=None)", "Stop one live plot"),
    ("live", "unfollow_all()", "Stop all live plots"),
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
        self._initial_conditions = [
            [float(coord) for coord in ic] for ic in initial_conditions
        ]

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
        live_plots = self._window.live_plot_controller.live_plots
        return live_plots[self.plot_name][self.trace_index]

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

    def _optional_help_table(self, data, table, name):
        if not table:
            return data

        self._window.jupyter_console_panel.tables.show(data, name=name)
        return data

    def help(self, table=False):
        data = pd.DataFrame(HELP_ROWS, columns=["category", "method", "description"])
        return self._optional_help_table(data, table, "System help")

    def examples(self, table=False):
        data = pd.DataFrame(EXAMPLE_ROWS, columns=["task", "commands"])
        return self._optional_help_table(data, table, "System examples")

    def summary(self, table=False):
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

        data = pd.Series(result)

        return self._optional_help_table(data, table, "System summary")

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
            solve_ics = [
                [float(coord) for coord in ic] for ic in self._initial_conditions()
            ]
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

    def radius(self, trajectory=None):
        rows = []
        for i in self._selected_trajectories(trajectory):
            solution = self.solution(i)
            radius = np.linalg.norm(solution, axis=1)
            rows.append(self._series_frame(i, {"radius": radius}))

        return self._concat_frames(rows, ["trajectory", "step", "t", "radius"])

    def displacement(self, trajectory=None):
        rows = []
        for i in self._selected_trajectories(trajectory):
            solution = self.solution(i)
            if len(solution) == 0:
                displacement = np.array([], dtype=np.float64)
            else:
                displacement = np.linalg.norm(solution - solution[0], axis=1)

            rows.append(self._series_frame(i, {"displacement": displacement}))

        return self._concat_frames(
            rows,
            ["trajectory", "step", "t", "displacement"],
        )

    def speed(self, trajectory=None):
        rows = []
        for i in self._selected_trajectories(trajectory):
            solution = self.solution(i)
            times = self.time(i)
            if len(solution) < 2:
                speed = np.zeros(len(solution), dtype=np.float64)
            else:
                velocity = np.gradient(solution, times, axis=0)
                speed = np.linalg.norm(velocity, axis=1)

            rows.append(self._series_frame(i, {"speed": speed}))

        return self._concat_frames(rows, ["trajectory", "step", "t", "speed"])

    def separation(self, a=0, b=1, *, log=False):
        sol_a = self.solution(a)
        sol_b = self.solution(b)
        length = min(len(sol_a), len(sol_b))
        distance = np.linalg.norm(sol_a[:length] - sol_b[:length], axis=1)
        if log:
            with np.errstate(divide="ignore"):
                distance = np.log(distance)
            value_column = "log_distance"
        else:
            value_column = "distance"

        return pd.DataFrame(
            {
                "trajectory_a": a,
                "trajectory_b": b,
                "step": np.arange(length),
                "t": self.time(a)[:length],
                value_column: distance,
            }
        )

    def separation_fit(
        self,
        a=0,
        b=1,
        *,
        t_min=None,
        t_max=None,
        step_min=None,
        step_max=None,
    ):
        frame = self._separation_fit_frame(
            a,
            b,
            t_min=t_min,
            t_max=t_max,
            step_min=step_min,
            step_max=step_max,
        )
        if len(frame) < 2:
            raise ValueError("At least two finite log-separation points are required")

        fit = self._fit_log_separation(frame)

        return pd.Series(
            {
                "trajectory_a": a,
                "trajectory_b": b,
                "slope": fit["slope"],
                "intercept": fit["intercept"],
                "r2": fit["r2"],
                "points": len(frame),
                "t_min": frame["t"].iloc[0],
                "t_max": frame["t"].iloc[-1],
                "step_min": int(frame["step"].iloc[0]),
                "step_max": int(frame["step"].iloc[-1]),
            }
        )

    def separation_summary(
        self,
        a=0,
        b=1,
        *,
        t_min=None,
        t_max=None,
        step_min=None,
        step_max=None,
    ):
        frame = self._separation_frame(
            a,
            b,
            t_min=t_min,
            t_max=t_max,
            step_min=step_min,
            step_max=step_max,
        )

        if frame.empty:
            return pd.Series(
                {
                    "trajectory_a": a,
                    "trajectory_b": b,
                    "points": 0,
                    "finite_points": 0,
                    "initial_distance": np.nan,
                    "final_distance": np.nan,
                    "min_distance": np.nan,
                    "median_distance": np.nan,
                    "max_distance": np.nan,
                    "growth_ratio": np.nan,
                    "log_slope": np.nan,
                    "log_intercept": np.nan,
                    "log_r2": np.nan,
                    "t_min": np.nan,
                    "t_max": np.nan,
                    "step_min": np.nan,
                    "step_max": np.nan,
                }
            )

        distance = frame["distance"].to_numpy(dtype=np.float64)
        finite = np.isfinite(distance)
        finite_distance = distance[finite]
        if finite_distance.size:
            min_distance = float(finite_distance.min())
            median_distance = float(np.median(finite_distance))
            max_distance = float(finite_distance.max())
        else:
            min_distance = median_distance = max_distance = np.nan

        initial_distance = float(distance[0])
        final_distance = float(distance[-1])
        if (
            np.isfinite(initial_distance)
            and initial_distance != 0.0
            and np.isfinite(final_distance)
        ):
            growth_ratio = final_distance / initial_distance
        else:
            growth_ratio = np.nan

        fit = self._separation_summary_fit(
            a,
            b,
            t_min=t_min,
            t_max=t_max,
            step_min=step_min,
            step_max=step_max,
        )

        return pd.Series(
            {
                "trajectory_a": a,
                "trajectory_b": b,
                "points": len(frame),
                "finite_points": int(finite.sum()),
                "initial_distance": initial_distance,
                "final_distance": final_distance,
                "min_distance": min_distance,
                "median_distance": median_distance,
                "max_distance": max_distance,
                "growth_ratio": growth_ratio,
                "log_slope": fit["slope"],
                "log_intercept": fit["intercept"],
                "log_r2": fit["r2"],
                "t_min": frame["t"].iloc[0],
                "t_max": frame["t"].iloc[-1],
                "step_min": int(frame["step"].iloc[0]),
                "step_max": int(frame["step"].iloc[-1]),
            }
        )

    def crossings(
        self,
        axis="z",
        value=None,
        *,
        direction="both",
        trajectory=None,
        t_max=None,
        n=None,
    ):
        axis_name = str(axis).lower()
        axis_col = axis_index(axis_name)
        direction = crossing_direction(direction)
        trajectory_data = self._crossing_trajectories(
            trajectory,
            t_max=t_max,
            n=n,
        )
        level = self._crossing_level(
            axis_col,
            value,
            [solution for _i, solution, _times in trajectory_data],
        )
        rows = []
        for i, solution, times in trajectory_data:
            if len(solution) < 2:
                continue

            crossings = plane_crossings(
                solution,
                axis_name,
                level,
                direction=direction,
                times=times,
            )
            for step, t, point, crossing_dir in zip(
                crossings.steps,
                crossings.times,
                crossings.points,
                crossings.directions,
                strict=True,
            ):
                rows.append(
                    {
                        "trajectory": i,
                        "axis": axis_name,
                        "level": level,
                        "direction": crossing_dir,
                        "step": int(step),
                        "t": t,
                        "x": point[0],
                        "y": point[1],
                        "z": point[2],
                    }
                )

        columns = [
            "trajectory",
            "axis",
            "level",
            "direction",
            "step",
            "t",
            *COORDINATE_COLUMNS,
        ]
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows, columns=columns)

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
            return self._register_live_plot(
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
            return self._register_live_plot(
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

    def plot_radius(
        self,
        *,
        trajectory=0,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            return self._register_live_plot(
                "radius",
                plot=plot,
                mode=plot_mode,
                trajectory=int(trajectory),
                pen=pen,
                label=label,
                zoom_region=zoom_region,
            )

        frame = self.radius(trajectory=trajectory)

        return self._plot_timeseries(
            frame["t"].to_numpy(),
            frame["radius"].to_numpy(),
            "radius",
            plot=plot,
            mode=plot_mode,
            pen=pen,
            label=label,
            zoom_region=zoom_region,
        )

    def plot_speed(
        self,
        *,
        trajectory=0,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            return self._register_live_plot(
                "speed",
                plot=plot,
                mode=plot_mode,
                trajectory=int(trajectory),
                pen=pen,
                label=label,
                zoom_region=zoom_region,
            )

        frame = self.speed(trajectory=trajectory)

        return self._plot_timeseries(
            frame["t"].to_numpy(),
            frame["speed"].to_numpy(),
            "speed",
            plot=plot,
            mode=plot_mode,
            pen=pen,
            label=label,
            zoom_region=zoom_region,
        )

    def plot_displacement(
        self,
        *,
        trajectory=0,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            return self._register_live_plot(
                "displacement",
                plot=plot,
                mode=plot_mode,
                trajectory=int(trajectory),
                pen=pen,
                label=label,
                zoom_region=zoom_region,
            )

        frame = self.displacement(trajectory=trajectory)

        return self._plot_timeseries(
            frame["t"].to_numpy(),
            frame["displacement"].to_numpy(),
            "displacement",
            plot=plot,
            mode=plot_mode,
            pen=pen,
            label=label,
            zoom_region=zoom_region,
        )

    def plot_separation(
        self,
        a=0,
        b=1,
        *,
        log=False,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            return self._register_live_plot(
                "separation",
                plot=plot,
                mode=plot_mode,
                a=int(a),
                b=int(b),
                log=bool(log),
                pen=pen,
                label=label,
                zoom_region=zoom_region,
            )

        frame = self.separation(a, b, log=log)
        value_column = "log_distance" if log else "distance"
        axis_label = f"log separation {a}-{b}" if log else f"separation {a}-{b}"

        return self._plot_timeseries(
            frame["t"].to_numpy(),
            frame[value_column].to_numpy(),
            axis_label,
            plot=plot,
            mode=plot_mode,
            pen=pen,
            label=label,
            zoom_region=zoom_region,
        )

    def plot_separation_fit(
        self,
        a=0,
        b=1,
        *,
        t_min=None,
        t_max=None,
        step_min=None,
        step_max=None,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        fit_pen=None,
        label=None,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            return self._register_live_plot(
                "separation_fit",
                plot=plot,
                mode=plot_mode,
                a=int(a),
                b=int(b),
                t_min=t_min,
                t_max=t_max,
                step_min=step_min,
                step_max=step_max,
                pen=pen,
                fit_pen=fit_pen,
                label=label,
            )

        fit = self.separation_fit(
            a,
            b,
            t_min=t_min,
            t_max=t_max,
            step_min=step_min,
            step_max=step_max,
        )
        target = self._plot_target(plot)
        self.plot_separation(
            a,
            b,
            log=True,
            plot=target,
            mode=plot_mode,
            pen=pen,
            label=label,
        )
        frame = self._separation_fit_frame(
            a,
            b,
            t_min=t_min,
            t_max=t_max,
            step_min=step_min,
            step_max=step_max,
        )
        fitted = fit["slope"] * frame["t"].to_numpy() + fit["intercept"]
        plot_kwargs = {}
        fit_line_pen = pen if fit_pen is None else fit_pen
        if fit_line_pen is not None:
            plot_kwargs["pen"] = fit_line_pen
        if label is not None:
            plot_kwargs["name"] = f"{label} fit"
        return self._plot_line(
            target,
            frame["t"].to_numpy(),
            fitted,
            mode=PLOT_MODE_OVERLAY,
            bottom="t",
            left=f"log separation fit {a}-{b}",
            **plot_kwargs,
        )

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

    def vector_field_slice(
        self,
        x_axis="x",
        y_axis="y",
        *,
        fixed_axis=None,
        fixed_value=0.0,
        x_range=None,
        y_range=None,
        density=21,
    ):
        x_name, y_name, fixed_name = self._slice_axes(x_axis, y_axis, fixed_axis)
        density = self._positive_int(density, "Density")
        if density < 2:
            raise ValueError("Density must be at least 2")
        x_range = self._vector_field_axis_range(x_name, x_range)
        y_range = self._vector_field_axis_range(y_name, y_range)

        x_values = np.linspace(x_range[0], x_range[1], density)
        y_values = np.linspace(y_range[0], y_range[1], density)
        xx, yy = np.meshgrid(x_values, y_values)
        states = np.zeros((density * density, 3), dtype=np.float64)
        states[:, AXES[x_name]] = xx.ravel()
        states[:, AXES[y_name]] = yy.ravel()
        states[:, AXES[fixed_name]] = float(fixed_value)

        config = self.config
        if config is None:
            raise ValueError("No attractor selected")
        params = np.ascontiguousarray(
            [self.values[param.name] for param in config.params],
            dtype=np.float64,
        )
        vectors = np.asarray(
            [config.equation(state, self.t_min, params) for state in states],
            dtype=np.float64,
        )
        u = vectors[:, AXES[x_name]]
        v = vectors[:, AXES[y_name]]
        return pd.DataFrame(
            {
                x_name: states[:, AXES[x_name]],
                y_name: states[:, AXES[y_name]],
                fixed_name: states[:, AXES[fixed_name]],
                "u": u,
                "v": v,
                "speed": np.hypot(u, v),
            }
        )

    def plot_vector_field(
        self,
        x_axis="x",
        y_axis="y",
        *,
        fixed_axis=None,
        fixed_value=0.0,
        x_range=None,
        y_range=None,
        density=21,
        live=False,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        pen=None,
        label=None,
        scale=0.75,
        colour_by_speed=False,
        speed_bands=5,
    ):
        plot_mode = self._plot_mode(mode)
        if live:
            x_name, y_name, fixed_name = self._slice_axes(
                x_axis,
                y_axis,
                fixed_axis,
            )
            return self._register_live_plot(
                "vector_field",
                plot=plot,
                mode=plot_mode,
                x_axis=x_name,
                y_axis=y_name,
                fixed_axis=fixed_name,
                fixed_value=float(fixed_value),
                x_range=(
                    None
                    if x_range is None
                    else tuple(float(value) for value in x_range)
                ),
                y_range=(
                    None
                    if y_range is None
                    else tuple(float(value) for value in y_range)
                ),
                density=int(density),
                pen=pen,
                label=label,
                scale=float(scale),
                colour_by_speed=bool(colour_by_speed),
                speed_bands=int(speed_bands),
            )

        frame = self.vector_field_slice(
            x_axis,
            y_axis,
            fixed_axis=fixed_axis,
            fixed_value=fixed_value,
            x_range=x_range,
            y_range=y_range,
            density=density,
        )
        x_name = str(x_axis).lower()
        y_name = str(y_axis).lower()
        target = self._plot_target(plot)
        if colour_by_speed:
            items = []
            for index, (x_data, y_data, band_pen) in enumerate(
                self._vector_field_speed_bands(
                    frame,
                    x_name,
                    y_name,
                    scale,
                    speed_bands,
                )
            ):
                items.append(
                    self._plot_line(
                        target,
                        x_data,
                        y_data,
                        mode=plot_mode if index == 0 else PLOT_MODE_OVERLAY,
                        bottom=x_name,
                        left=y_name,
                        pen=band_pen,
                    )
                )
            return tuple(items)

        x_data, y_data = self._vector_field_segments(frame, x_name, y_name, scale)
        plot_kwargs = {}
        if pen is not None:
            plot_kwargs["pen"] = pen
        if label is not None:
            plot_kwargs["name"] = str(label)
        return self._plot_line(
            target,
            x_data,
            y_data,
            mode=plot_mode,
            bottom=x_name,
            left=y_name,
            **plot_kwargs,
        )

    def live_plots(self):
        return self._window.live_plot_controller._live_plot_frame()

    def unfollow(self, plot=None):
        return self._window.live_plot_controller._clear_live_plot(plot)

    def unfollow_all(self):
        return self._window.live_plot_controller._clear_all_live_plots()

    def _crossing_level(self, axis_col, value, solutions=None):
        if value is not None:
            return float(value)

        if solutions is None:
            solutions = self.solutions
        if not solutions:
            return 0.0
        values = np.concatenate([solution[:, axis_col] for solution in solutions])
        values = values[np.isfinite(values)]
        if len(values) == 0:
            return 0.0

        return float((values.min() + values.max()) / 2)

    def _slice_axes(self, x_axis, y_axis, fixed_axis):
        x_name = str(x_axis).lower()
        y_name = str(y_axis).lower()
        axis_index(x_name)
        axis_index(y_name)

        if x_name == y_name:
            raise ValueError("Slice axes must be different")

        if fixed_axis is None:
            fixed_name = next(
                axis for axis in COORDINATE_COLUMNS if axis not in {x_name, y_name}
            )
        else:
            fixed_name = str(fixed_axis).lower()
            axis_index(fixed_name)
        if fixed_name in {x_name, y_name}:
            raise ValueError("Fixed axis must be different from slice axes")

        return x_name, y_name, fixed_name

    def _vector_field_axis_range(self, axis, explicit_range):
        if explicit_range is not None:
            low, high = explicit_range
            return float(low), float(high)

        bounds = self.bounds()
        if axis not in bounds.index:
            return -20.0, 20.0

        low = bounds.loc[axis, "min"]
        high = bounds.loc[axis, "max"]
        if not np.isfinite(low) or not np.isfinite(high):
            return -20.0, 20.0
        if low == high:
            span = max(abs(float(low)), 1.0)
            padding = span * 0.5
        else:
            padding = (float(high) - float(low)) * 0.05

        return float(low) - padding, float(high) + padding

    def _positive_int(self, value, label):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a positive integer") from exc
        if parsed <= 0:
            raise ValueError(f"{label} must be a positive integer")

        return parsed

    def _non_negative_int(self, value, label):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a non-negative integer") from exc
        if parsed < 0:
            raise ValueError(f"{label} must be a non-negative integer")

        return parsed

    def _plot_timeseries(
        self,
        times,
        values,
        axis_label,
        *,
        plot,
        mode,
        pen,
        label=None,
        zoom_region=False,
    ):
        plot_kwargs = {}
        if pen is not None:
            plot_kwargs["pen"] = pen
        if label is not None:
            plot_kwargs["name"] = str(label)
        return self._plot_line(
            self._plot_target(plot),
            times,
            values,
            mode=mode,
            bottom="t",
            left=axis_label,
            zoom_region=zoom_region,
            **plot_kwargs,
        )

    def _plot_mode(self, mode=PLOT_MODE_REPLACE):
        normalised = str(mode).strip().lower()
        if normalised == PLOT_MODE_REPLACE:
            return PLOT_MODE_REPLACE
        if normalised == PLOT_MODE_OVERLAY:
            return PLOT_MODE_OVERLAY

        raise ValueError("Plot mode must be 'replace' or 'overlay'")

    def _plot_target(self, plot):
        if plot is not None:
            if isinstance(plot, str):
                plots = self._window.jupyter_console_panel.plots
                try:
                    return plots.get(plot)
                except KeyError:
                    return plots.new(plot)
            return plot

        return self._window.jupyter_console_panel.plot

    def _plot_line(
        self,
        target,
        x,
        y,
        *,
        mode,
        bottom,
        left,
        zoom_region=False,
        **kwargs,
    ):
        if isinstance(target, ConsolePlot):
            return target.line(
                x,
                y,
                mode=mode,
                bottom=bottom,
                left=left,
                zoom_region=zoom_region,
                **kwargs,
            )

        if mode == PLOT_MODE_REPLACE:
            target.clear()
        item = target.plot(x, y, **kwargs)
        target.setLabel("bottom", bottom)
        target.setLabel("left", left)
        return item

    def _plot_scatter(self, target, x, y, *, mode, bottom, left, **kwargs):
        if isinstance(target, ConsolePlot):
            symbol_size = kwargs.pop("symbolSize", None)
            return target.scatter(
                x,
                y,
                mode=mode,
                bottom=bottom,
                left=left,
                symbol_size=symbol_size,
                **kwargs,
            )

        if mode == PLOT_MODE_REPLACE:
            target.clear()
        item = target.plot(x, y, **kwargs)
        target.setLabel("bottom", bottom)
        target.setLabel("left", left)
        return item

    def _vector_field_segments(self, frame, x_axis, y_axis, scale):
        x = frame[x_axis].to_numpy(dtype=np.float64)
        y = frame[y_axis].to_numpy(dtype=np.float64)
        u = frame["u"].to_numpy(dtype=np.float64)
        v = frame["v"].to_numpy(dtype=np.float64)
        speed = np.hypot(u, v)
        finite = np.isfinite(speed) & (speed > 0)
        if not finite.any():
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

        x = x[finite]
        y = y[finite]
        u = u[finite]
        v = v[finite]
        speed = speed[finite]

        unique_x = np.unique(x)
        unique_y = np.unique(y)
        dx = np.diff(unique_x).min() if len(unique_x) > 1 else 1.0
        dy = np.diff(unique_y).min() if len(unique_y) > 1 else 1.0
        length = min(abs(dx), abs(dy)) * float(scale)

        nx = u / speed
        ny = v / speed
        x0 = x - 0.5 * length * nx
        y0 = y - 0.5 * length * ny
        x1 = x + 0.5 * length * nx
        y1 = y + 0.5 * length * ny

        head_length = length * 0.25
        head_width = length * 0.12
        base_x = x1 - head_length * nx
        base_y = y1 - head_length * ny
        perp_x = -ny
        perp_y = nx
        left_x = base_x + head_width * perp_x
        left_y = base_y + head_width * perp_y
        right_x = base_x - head_width * perp_x
        right_y = base_y - head_width * perp_y

        nan_x = np.full_like(x0, np.nan)
        nan_y = np.full_like(y0, np.nan)
        return (
            np.column_stack(
                [
                    x0,
                    x1,
                    nan_x,
                    x1,
                    left_x,
                    nan_x,
                    x1,
                    right_x,
                    nan_x,
                ]
            ).ravel(),
            np.column_stack(
                [
                    y0,
                    y1,
                    nan_y,
                    y1,
                    left_y,
                    nan_y,
                    y1,
                    right_y,
                    nan_y,
                ]
            ).ravel(),
        )

    def _vector_field_speed_bands(
        self,
        frame,
        x_axis,
        y_axis,
        scale,
        speed_bands,
    ):
        band_count = self._positive_int(speed_bands, "Speed band count")
        if band_count < 2:
            raise ValueError("Speed band count must be at least 2")

        speeds = frame["speed"].to_numpy(dtype=np.float64)
        finite_speeds = speeds[np.isfinite(speeds)]
        if len(finite_speeds) == 0:
            empty = (np.array([], dtype=np.float64), np.array([], dtype=np.float64))
            return [
                (*empty, self._vector_field_speed_pen(index, band_count))
                for index in range(band_count)
            ]

        low = float(finite_speeds.min())
        high = float(finite_speeds.max())
        edges = np.linspace(low, high, band_count + 1)
        rows = []
        for index in range(band_count):
            if low == high:
                mask = (
                    np.isfinite(speeds)
                    if index == band_count - 1
                    else np.zeros(len(speeds), dtype=bool)
                )
            elif index == band_count - 1:
                mask = (speeds >= edges[index]) & (speeds <= edges[index + 1])
            else:
                mask = (speeds >= edges[index]) & (speeds < edges[index + 1])
            x_data, y_data = self._vector_field_segments(
                frame.loc[mask],
                x_axis,
                y_axis,
                scale,
            )
            rows.append(
                (x_data, y_data, self._vector_field_speed_pen(index, band_count))
            )
        return rows

    def _vector_field_speed_pen(self, index, band_count):
        if band_count <= len(VECTOR_FIELD_SPEED_PENS):
            return VECTOR_FIELD_SPEED_PENS[index]
        palette_index = round(
            index * (len(VECTOR_FIELD_SPEED_PENS) - 1) / (band_count - 1)
        )
        return VECTOR_FIELD_SPEED_PENS[palette_index]

    def _register_live_plot(self, kind, *, plot=None, **options):
        mode = self._plot_mode(options.pop("mode", PLOT_MODE_REPLACE))
        registration = self._window.live_plot_controller._register_live_plot(
            kind,
            plot=plot,
            mode=mode,
            **options,
        )
        return self._live_plot_handle_or_registration(
            registration,
            plot=plot,
            mode=mode,
        )

    def _live_plot_handle_or_registration(self, registration, *, plot, mode):
        live_plots = self._window.live_plot_controller.live_plots

        plot_name = None
        if isinstance(registration, pd.Series | dict):
            plot_name = registration.get("plot")
        if not plot_name:
            plot_name = plot
        if not plot_name:
            plot_name = self._window.jupyter_console_panel.plots.current_name
        if not plot_name or plot_name not in live_plots:
            return registration

        specs = live_plots[plot_name]
        trace_index = len(specs) - 1 if mode == PLOT_MODE_OVERLAY else 0

        if not 0 <= trace_index < len(specs):
            return registration

        return LivePlotHandle(self._window, plot_name, trace_index)

    def _separation_frame(
        self,
        a,
        b,
        *,
        t_min=None,
        t_max=None,
        step_min=None,
        step_max=None,
    ):
        frame = self.separation(a, b)
        if t_min is not None:
            frame = frame[frame["t"] >= t_min]
        if t_max is not None:
            frame = frame[frame["t"] <= t_max]
        if step_min is not None:
            frame = frame[frame["step"] >= step_min]
        if step_max is not None:
            frame = frame[frame["step"] <= step_max]
        return frame.reset_index(drop=True)

    def _separation_fit_frame(
        self,
        a,
        b,
        *,
        t_min=None,
        t_max=None,
        step_min=None,
        step_max=None,
    ):
        frame = self.separation(a, b, log=True)
        mask = np.isfinite(frame["log_distance"].to_numpy())
        if t_min is not None:
            mask &= frame["t"].to_numpy() >= t_min
        if t_max is not None:
            mask &= frame["t"].to_numpy() <= t_max
        if step_min is not None:
            mask &= frame["step"].to_numpy() >= step_min
        if step_max is not None:
            mask &= frame["step"].to_numpy() <= step_max

        return frame.loc[mask].reset_index(drop=True)

    def _separation_summary_fit(self, a, b, **filters):
        frame = self._separation_fit_frame(a, b, **filters)
        if len(frame) < 2:
            return {"slope": np.nan, "intercept": np.nan, "r2": np.nan}

        return self._fit_log_separation(frame)

    def _fit_log_separation(self, frame):
        slope, intercept = np.polyfit(frame["t"], frame["log_distance"], 1)
        predicted = slope * frame["t"] + intercept
        residual = frame["log_distance"] - predicted
        total = frame["log_distance"] - frame["log_distance"].mean()
        ss_res = np.sum(residual**2)
        ss_tot = np.sum(total**2)
        r2 = 1.0 if ss_tot == 0.0 and ss_res == 0.0 else 1.0 - ss_res / ss_tot

        return {"slope": slope, "intercept": intercept, "r2": r2}

    def _selected_trajectories(self, trajectory):
        solutions = self.solutions
        if trajectory is None:
            return range(len(solutions))

        self.solution(trajectory)

        return [trajectory]

    def _variant_values(self, values):
        variant_values = dict(self.values)
        if values is None:
            return variant_values
        if not isinstance(values, dict):
            raise TypeError("Parameter overrides must be a dictionary")

        valid_names = {param.name for param in self.config.params}
        unknown = sorted(set(values) - valid_names)
        if unknown:
            names = ", ".join(unknown)
            raise ValueError(f"Unknown parameter override(s): {names}")

        for name, value in values.items():
            try:
                variant_values[name] = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter {name} must be numeric") from exc

        return variant_values

    def _crossing_trajectories(self, trajectory, *, t_max=None, n=None):
        rows = []

        if t_max is None and n is None:
            for i in self._selected_trajectories(trajectory):
                rows.append((i, self.solution(i), self.time(i)))
            return rows

        config = self.config
        if config is None:
            return rows

        solve_n = self._positive_int(self.n if n is None else n, "n")
        solve_t_max = self.t_max if t_max is None else float(t_max)
        if solve_t_max <= self.t_min:
            raise ValueError("t_max must be greater than t_min")

        initial_conditions = self._initial_conditions()
        if trajectory is None:
            selected = range(len(initial_conditions))
        else:
            selected = [
                self._trajectory_index_from_initial_conditions(
                    trajectory,
                    initial_conditions,
                )
            ]

        for i in selected:
            solution = solve_attractor(
                config,
                self.values,
                solve_n,
                t_max=solve_t_max,
                ic=initial_conditions[i],
            )
            times = _solver_sample_times(self.t_min, solve_t_max, len(solution))
            rows.append((i, solution, times))

        return rows

    def _trajectory_index_from_initial_conditions(self, trajectory, initial_conditions):
        try:
            index = int(trajectory)
        except (TypeError, ValueError) as exc:
            raise IndexError(f"No trajectory at index {trajectory}") from exc
        if index < 0 or index >= len(initial_conditions):
            raise IndexError(f"No trajectory at index {trajectory}")
        return index

    def _series_frame(self, trajectory, columns):
        first = next(iter(columns.values()))
        length = len(first)
        frame = pd.DataFrame(columns)
        frame.insert(0, "t", self.time(trajectory)[:length])
        frame.insert(0, "step", np.arange(length))
        frame.insert(0, "trajectory", trajectory)

        return frame

    def _concat_frames(self, rows, columns):
        if not rows:
            return pd.DataFrame(columns=columns)

        return pd.concat(rows, ignore_index=True)

    def _initial_conditions(self):
        trajectories = self._window.controls.trajectory_panel.get_trajectories()
        if trajectories:
            return [trajectory["ic"] for trajectory in trajectories]

        config = self.config
        if config is None:
            return []

        return [config.initial_conditions]

    def _trajectory_metadata(self):
        rows = []
        for index, trajectory in enumerate(
            self._window.controls.trajectory_panel.get_trajectories() or []
        ):
            colour = trajectory.get("colour")
            if colour is not None:
                colour = colour.name()
            rows.append(
                {
                    "label": trajectory.get("label", f"T{index}"),
                    "colour": colour,
                    "alpha": trajectory.get("alpha"),
                    "render_mode": trajectory.get("render_mode"),
                    "n": trajectory.get("n"),
                    "t_max": trajectory.get("t_max"),
                }
            )

        return rows

    def _trajectory_solve_spec(self, index):
        state = dict(self._window._solve_state)
        specs = state.get("trajectory_specs")
        if isinstance(specs, list):
            try:
                spec = specs[index]
            except IndexError:
                spec = None
            if isinstance(spec, dict):
                return dict(spec)

        return {"n": self.n, "t_max": self.t_max}

    def _coordinate(self, initial_conditions, trajectory, axis):
        try:
            return initial_conditions[trajectory][axis]
        except (IndexError, TypeError):
            return None

    def _sample_indices(self, length, sample_size):
        if length <= sample_size:
            return np.arange(length)

        return np.linspace(0, length - 1, sample_size, dtype=int)

    def _trajectory_columns(self):
        columns = [
            "trajectory",
            "label",
            "colour",
            "alpha",
            "render_mode",
            "n",
            "t_max",
            "length",
            "initial_x",
            "initial_y",
            "initial_z",
            "final_x",
            "final_y",
            "final_z",
        ]
        for axis in COORDINATE_COLUMNS:
            columns.extend([f"{axis}_min", f"{axis}_max"])

        return columns
