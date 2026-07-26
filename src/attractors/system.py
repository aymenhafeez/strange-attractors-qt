import numpy as np
import pandas as pd

AXES = {"x": 0, "y": 1, "z": 2}
COORDINATE_COLUMNS = ["x", "y", "z"]


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
