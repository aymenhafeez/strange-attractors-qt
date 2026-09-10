import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtGui

from ..colour import colourmap
from ..ui.style import plot_colours

STATIC_RENDER_MAX_POINTS = 80000
ANIM_RENDER_MAX_POINTS = 30000
COLOUR_MODES = {"solid", "speed", "x", "y", "z"}


def _decimate_indices(n_points, max_points):
    if n_points <= max_points:
        return None

    return np.linspace(0, n_points - 1, max_points, dtype=np.int64)


def _decimate_for_display(points, max_points):
    idx = _decimate_indices(len(points), max_points)
    if idx is None:
        return points

    return points[idx]


class TrajectoryRenderer:
    def __init__(self, view, timer_active):
        self.view = view
        self._timer_active = timer_active
        self._solutions = None
        self._scatters = []
        self._lines = []
        self._heads = []
        self._trajectories = []
        self._base_colour = plot_colours()["trajectory"]
        self._current_alpha = 1.0
        self._current_line_width = 1.0
        self._line_mode = False
        self._trail_mode = False
        self._colour_mode = "solid"
        self._colourmap = "viridis"
        self._time_steps = []
        self._solution_colours = []
        self._particle_colours = []
        self._heads_visible = True
        self._traj_tail_length = 5000
        self._traj_tail_enabled = False
        self._colour_cache = {}

    @property
    def solutions(self):
        return self._solutions

    def sync_gl_items(self, n):
        while len(self._scatters) < n:
            scatter = gl.GLScatterPlotItem(size=1.0)
            scatter.setGLOptions(
                "additive" if plot_colours()["is_dark"] else "translucent"
            )
            scatter.setVisible(not self._line_mode)
            self.view.addItem(scatter)
            self._scatters.append(scatter)
            line = gl.GLLinePlotItem()
            line.setGLOptions(
                "additive" if plot_colours()["is_dark"] else "translucent"
            )
            line.setVisible(self._line_mode)
            self.view.addItem(line)
            self._lines.append(line)
        while len(self._scatters) > n:
            self.view.removeItem(self._scatters.pop())
            self.view.removeItem(self._lines.pop())
        while len(self._heads) < n:
            head = gl.GLScatterPlotItem(size=20.0)
            head.setGLOptions(
                "additive" if plot_colours()["is_dark"] else "translucent"
            )
            self.view.addItem(head)
            self._heads.append(head)
        while len(self._heads) > n:
            self.view.removeItem(self._heads.pop())
        self.sync_head_visibility()

    def set_line_mode(self, checked):
        self._line_mode = checked
        for index, (scatter, line) in enumerate(zip(self._scatters, self._lines)):
            line_mode = self._trajectory_line_mode(index)
            line.setVisible(line_mode)
            scatter.setVisible(not line_mode)

    def set_point_mode(self, checked):
        self._heads_visible = checked
        self.sync_head_visibility()

    def sync_head_visibility(self):
        visible = self._heads_visible and self._timer_active()
        for head in self._heads:
            head.setVisible(visible)

    def set_line_width(self, val):
        self._current_line_width = val
        for line in self._lines:
            line.setData(width=self._current_line_width)

    def set_alpha(self, val):
        self._current_alpha = val / 100.0 if val > 1 else val
        self.refresh_colours()

    def set_colour_mode(self, mode):
        if mode not in COLOUR_MODES:
            raise ValueError(f"Unknown colour mode: {mode}")
        if mode == self._colour_mode:
            return

        self._colour_mode = mode
        self.refresh_colours()

    def set_colourmap(self, name):
        if name == self._colourmap:
            return

        self._colourmap = name
        self.refresh_colours()

    def set_time_steps(self, time_steps):
        self._time_steps = [value for value in time_steps]

    def set_trajectories(self, trajectories):
        self._trajectories = trajectories
        self._rebuild_solution_colours()

    def _time_step(self, index):
        if index >= len(self._time_steps):
            return 1.0

        time_step = self._time_steps[index]
        if not np.isfinite(time_step) or time_step <= 0.0:
            return 1.0

        return time_step

    def _speed_values(self, index, solution):
        if len(solution) < 2:
            return np.zeros(len(solution))

        velocity = np.gradient(solution, self._time_step(index), axis=0)

        return np.linalg.norm(velocity, axis=1)

    def _colour_values(self, index, solution):
        if self._colour_mode == "speed":
            return self._speed_values(index, solution)

        coordinate_axes  = {"x": 0, "y": 1, "z": 2}
        axis = coordinate_axes.get(self._colour_mode)
        return solution[:, axis]

    def _build_solution_colours(self, solutions):
        if self._colour_mode == "solid":
            return [
                self._solid_colour_array(index, len(solution))
                for index, solution in enumerate(solutions)
            ]

        values = [
            self._colour_values(index, solution)
            for index, solution in enumerate(solutions)
        ]

        non_empty = [value for value in values if len(value)]
        if not non_empty:
            return [np.empty((0, 4)) for _ in solutions]

        vmin = min(value.min() for value in non_empty)
        vmax = max(value.max() for value in non_empty)

        colours = []
        for index, value in enumerate(values):
            # not using base_colour in mapped mode, per trajectory alpha still applies
            _base_colour, alpha = self.get_traj_colour_alpha(index)
            colours.append(
                colourmap(value, self._colourmap, alpha=alpha, vmin=vmin, vmax=vmax)
            )

        return colours

    def _rebuild_solution_colours(self):
        if not self._solutions:
            self._solution_colours = []
            self._particle_colours = []
            return

        self._solution_colours = self._build_solution_colours(self._solutions)
        self._particle_colours = self._build_particle_colours(self._solution_colours)

    def _build_particle_colours(self, solution_colours):
        particle_colours = []

        for (
            i,
            colours,
        ) in enumerate(solution_colours):
            colours = colours.copy()
            colours[:, 3] = self.get_particle_alpha(i)
            particle_colours.append(colours)

        return particle_colours

    def _trajectory_line_mode(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None
        if traj is None:
            return self._line_mode
        mode = traj.get("render_mode")
        if mode is None:
            return self._line_mode
        return str(mode).lower() == "line"

    def get_traj_colour_alpha(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None
        qc = traj.get("colour") if traj is not None else None
        if isinstance(qc, QtGui.QColor):
            base_colour = (qc.redF(), qc.greenF(), qc.blueF())
            alpha = self._current_alpha * traj.get("alpha", 1.0)
        else:
            base_colour = self._base_colour
            if traj:
                alpha = self._current_alpha * traj.get("alpha", 1.0)
            else:
                alpha = self._current_alpha
        return base_colour, alpha

    def get_particle_alpha(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None

        if traj is None:
            return 1.0

        return traj.get("alpha", 1.0)

    def get_particle_colours(self, index):
        if index >= len(self._particle_colours):
            return np.empty((0, 4))

        return self._particle_colours[index]

    def get_colour_array(self, n, alpha, base_colour):
        colour_key = tuple(round(c, 6) for c in base_colour)
        key = (n, round(alpha, 6), colour_key)

        cached = self._colour_cache.get(key)
        if cached is not None:
            return cached

        colour = np.full((n, 4), (*base_colour, alpha))
        self._colour_cache[key] = colour

        return colour

    def _solid_colour_array(self, index, length):
        base_colour, alpha = self.get_traj_colour_alpha(index)
        return self.get_colour_array(length, alpha, base_colour)

    def _apply_trail_fade(self, colours):
        if not self._trail_mode or len(colours) == 0:
            return colours

        faded = colours.copy()
        faded[:, 3] *= np.linspace(0.0, 1.0, len(faded))

        return faded

    def refresh_colours(self):
        self._rebuild_solution_colours()
        self.update_display()

    def display_solutions(self, solutions, is_partial):
        solution_colours = self._build_solution_colours(solutions)

        if not is_partial:
            self._solutions = solutions
            self._solution_colours = solution_colours
            self._particle_colours = self._build_particle_colours(solution_colours)

        self.sync_gl_items(len(solutions))

        for index, (solution, colours) in enumerate(zip(solutions, solution_colours)):
            segment, segment_colours = self.get_traj_tail_data(solution, colours)
            self._set_trajectory_data(index, pos=segment, colour=segment_colours)

    def clear_solutions(self):
        self._solutions = None
        self._solution_colours = []
        self._particle_colours = []
        self.sync_gl_items(0)

    def get_traj_tail_data(self, solution, colours):
        if self._traj_tail_enabled:
            segment = solution[-self._traj_tail_length :]
            segment_colours = colours[-self._traj_tail_length :]
        else:
            segment = solution
            segment_colours = colours

        indices = _decimate_indices(len(segment), STATIC_RENDER_MAX_POINTS)
        if indices is not None:
            segment = segment[indices]
            segment_colours = segment_colours[indices]

        segment_colours = self._apply_trail_fade(segment_colours)

        return segment, segment_colours

    def set_trail_mode(self, checked):
        self._trail_mode = checked
        self._traj_tail_enabled = checked
        self.update_display()

    def set_traj_tail_length(self, val):
        self._traj_tail_length = val
        self.update_display()

    def update_display(self):
        if not self._solutions:
            return

        if len(self._solution_colours) != len(self._solutions):
            self._rebuild_solution_colours()

        for index, (solution, colours) in enumerate(
            zip(self._solutions, self._solution_colours)
        ):
            segment, segment_colours = self.get_traj_tail_data(solution, colours)
            self._set_trajectory_data(index, pos=segment, colour=segment_colours)

    def _trajectory_size(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None

        size = 1.0
        if traj is None:
            return size

        return traj.get("size", size)

    def _trajectory_line_width(self, i):
        traj = self._trajectories[i] if i < len(self._trajectories) else None

        if traj is None:
            return self._current_line_width

        return traj.get("size", self._current_line_width)

    def _set_trajectory_data(self, i, *, pos=None, colour=None):
        if i >= len(self._scatters):
            return

        line_mode = self._trajectory_line_mode(i)
        kwargs = {}
        if pos is not None:
            kwargs["pos"] = pos
        if colour is not None:
            kwargs["color"] = colour

        self._scatters[i].setData(size=self._trajectory_size(i), **kwargs)
        self._scatters[i].setVisible(not line_mode)
        self._lines[i].setData(width=self._trajectory_size(i), **kwargs)
        self._lines[i].setVisible(line_mode)

        if i < len(self._heads) and colour is not None:
            head_kwargs = {"color": colour[-1:]}
            if pos is not None:
                head_kwargs["pos"] = pos[-1:]
            self._heads[i].setData(**head_kwargs)

    def render_animation_frame(self, frame):
        if not self._solutions:
            return []

        all_segments = []

        for index, (solution, colours) in enumerate(
            zip(self._solutions, self._solution_colours)
        ):
            if self._traj_tail_enabled:
                start = max(0, frame - self._traj_tail_length)
            else:
                start = 0

            segment = solution[start:frame]
            render_colours = colours[start:frame]

            indices = _decimate_indices(
                len(segment),
                ANIM_RENDER_MAX_POINTS,
            )
            if indices is not None:
                render_segment = segment[indices]
                render_colours = render_colours[indices]
            else:
                render_segment = segment

            render_colours = self._apply_trail_fade(render_colours)

            if index < len(self._scatters):
                self._scatters[index].setData(
                    pos=render_segment,
                    color=render_colours,
                    size=self._trajectory_size(index),
                )
                self._lines[index].setData(
                    pos=render_segment,
                    color=render_colours,
                    width=self._trajectory_size(index),
                )

            if index < len(self._heads):
                self._heads[index].setData(
                    pos=render_segment[-1:],
                    color=render_colours[-1:],
                )

            all_segments.append(segment)

        return all_segments

    def apply_theme(self):
        colours = plot_colours()
        self._base_colour = colours["trajectory"]
        self._colour_cache.clear()

        gl_options = "additive" if colours["is_dark"] else "translucent"
        for scatter in self._scatters:
            scatter.setGLOptions(gl_options)
        for line in self._lines:
            line.setGLOptions(gl_options)
        for head in self._heads:
            head.setGLOptions(gl_options)

        self.refresh_colours()
