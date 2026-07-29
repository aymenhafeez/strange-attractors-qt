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
        "plot_axis(axis, live=True, append=False)",
        "Keep an axis time series plot linked to main",
    ),
    (
        "live",
        "plot_radius(live=True) / plot_speed(live=True)",
        "Keep geometry time series plots linked to main",
    ),
    (
        "live",
        "plot_projection(x_axis, y_axis, live=True, append=False)",
        "Keep a phase plot linked to main",
    ),
    (
        "live",
        "plot_separation(a=0, b=1, live=True, append=False)",
        "Keep separation linked to main",
    ),
    (
        "live",
        "plot_separation_fit(a=0, b=1, live=True, append=False)",
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
    ("Live z while sliders move", "system.plot_axis('z', live=True)"),
    (
        "Overlay coordinates",
        (
            "system.plot_axis('x', live=True, plot='coords', pen='r', label='x'); "
            "system.plot_axis("
            "'y', live=True, plot='coords', append=True, pen='g', label='y'"
            "); "
            "system.plot_axis("
            "'z', live=True, plot='coords', append=True, pen='b', label='z'"
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


def _read_only_view(solution):
    view = np.asarray(solution).view()
    view.setflags(write=False)

    return view


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


def _copy_initial_conditions(initial_conditions):
    return [[float(coord) for coord in ic] for ic in initial_conditions]


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
        return self._window._lab_live_plots[self.plot_name][self.trace_index]

    @property
    def item(self):
        items = self._window._lab_live_item_cache()
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
            if hasattr(item, "setPen"):
                item.setPen(pen)

        return self

    def setVisible(self, visible):
        for item in self.items:
            if hasattr(item, "setVisible"):
                item.setVisible(bool(visible))

        return self

    def setAlpha(self, alpha, auto=False):
        for item in self.items:
            if hasattr(item, "setAlpha"):
                item.setAlpha(float(alpha), auto=auto)

        return self

    def unfollow(self):
        remove = self._window._remove_lab_live_trace
        return remove(self.plot_name, self.trace_index)

    def __getattr__(self, name):
        item = self.item
        if item is None:
            raise AttributeError(name)
        if isinstance(item, tuple):
            raise TypeError(
                f"Live plot has {len(item)} items; use .items or a handle method",
            )

        return getattr(item, name)


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
