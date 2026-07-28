import numpy as np
import pandas as pd

HELP_ROWS = [
    ("context", "summary()", "Current system, solve size, bounds and camera"),
    ("context", "status()", "Solve freshness and last error state"),
    ("context", "describe()", "System description and equation text"),
    ("context", "parameters()", "Parameter values, defaults and ranges"),
    ("control", "set_parameter(name, value, solve=False)", "Update a main parameter"),
    ("control", "set_parameters(values, solve=False)", "Update main parameters"),
    ("control", "set_time(n=None, t_max=None, solve=False)", "Update main solve time"),
    ("control", "set_n(n, solve=False)", "Update main sample count"),
    ("control", "set_t_max(t_max, solve=False)", "Update main solve duration"),
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
    ("plotting", "plot_axis(axis)", "Coordinate over time"),
    ("plotting", "plot_radius() / plot_speed()", "Geometry time series plots"),
    ("plotting", "plot_displacement()", "Displacement over time"),
    ("plotting", "plot_separation()", "Trajectory separation over time"),
    ("plotting", "plot_separation_fit()", "Log separation with fitted line"),
    ("plotting", "plot_crossings()", "Plane crossings as a 2D section"),
    ("plotting", "plot_vector_field()", "Vector field on a 2D phase space slice"),
    ("plotting", "plot_returns() / plot_return_lags()", "Recurrence plots"),

EXAMPLE_ROWS = [
    (
        "Inspect current system",
        "system.summary(); system.parameters(); system.trajectories()",
    ),
    ("Plot a phase projection", "system.plot_xz()"),
    ("Plot a coordinate over time", "system.plot_axis('z')"),
    ("Set a parameter and solve", "system.set_parameter('rho', 32, solve=True)"),
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
            "system.plot_separation_fit(0, 2, pen='y', clear=False)"
        ),
    ),
    (
        "Find recurrent states",
        "system.return_lag_summary(); system.nearest_returns(count=50)",
    ),
    ("Plot return durations", "system.plot_return_lags(count=100)"),
]
]


def _read_only_view(solution):
    view = np.asarray(solution).view()
    view.setflags(write=False)

    return view


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
        return config

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
        return self._window.scene.get_camera_state()

    @property
    def solutions(self):
        solutions = self._window.scene.get_solutions() or []
        return tuple(_read_only_view(solution) for solution in solutions)

    @property
    def has_solutions(self):
        return bool(self.solutions)

    def help(self):
        return pd.DataFrame(HELP_ROWS, columns=["category", "method", "description"])

    def examples(self):
        return pd.DataFrame(EXAMPLE_ROWS, columns=["task", "commands"])

    def solution(self, index=0, *, copy=False):
        solutions = self.solutions
        try:
            solution = solutions[index]
        except IndexError as exc:
            raise IndexError(f"No trajectory at index {index}") from exc
        if copy:
            return solution.copy()
        return solution

    def current_solution(self, *, copy=False):
        return self.solution(0, copy=copy)

    def time(self, index=0):
        solution = self.solution(index)
        return np.linspace(self.t_min, self.t_max, len(solution))

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

    def plot_projection(
        self,
        x_axis="x",
        y_axis="y",
        *,
        trajectory=0,
        plot_widget=None,
        clear=True,
        pen=None,
    ):
        x_col = self._axis_index(x_axis)
        y_col = self._axis_index(y_axis)
        solution = self.solution(trajectory)
        target = plot_widget or self._window.jupyter_console_panel.plot_widget
        if clear:
            target.clear()
        plot_kwargs = {}
        if pen is not None:
            plot_kwargs["pen"] = pen
        item = target.plot(solution[:, x_col], solution[:, y_col], **plot_kwargs)
        target.setLabel("bottom", str(x_axis))
        target.setLabel("left", str(y_axis))
        return item

    def plot_xy(self, **kwargs):
        return self.plot_projection("x", "y", **kwargs)

    def plot_xz(self, **kwargs):
        return self.plot_projection("x", "z", **kwargs)

    def plot_yz(self, **kwargs):
        return self.plot_projection("y", "z", **kwargs)

    def _axis_index(self, axis):
        try:
            return AXES[str(axis).lower()]
        except KeyError as exc:
            raise ValueError("Axis must be one of x, y or z") from exc
