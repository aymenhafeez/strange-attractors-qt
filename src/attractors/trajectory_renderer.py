import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtGui

STATIC_RENDER_MAX_POINTS = 80000
ANIM_RENDER_MAX_POINTS = 30000


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
        self._base_colour = (1.0, 1.0, 1.0)
        self._current_alpha = 1.0
        self._line_mode = False
        self._trail_mode = False
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
            scatter.setGLOptions("additive")
            scatter.setVisible(not self._line_mode)
            self.view.addItem(scatter)
            self._scatters.append(scatter)
            line = gl.GLLinePlotItem()
            line.setVisible(self._line_mode)
            self.view.addItem(line)
            self._lines.append(line)
        while len(self._scatters) > n:
            self.view.removeItem(self._scatters.pop())
            self.view.removeItem(self._lines.pop())
        while len(self._heads) < n:
            head = gl.GLScatterPlotItem(size=20.0)
            head.setGLOptions("additive")
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

    def set_alpha(self, val):
        self._current_alpha = val / 100.0 if val > 1 else val
        self.refresh_colours()

    def set_trajectories(self, trajectories):
        self._trajectories = trajectories

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

    def plot_trail(self, n, alpha=1.0, base_colour=None):
        if base_colour is None:
            base_colour = self._base_colour
        colour = np.zeros((n, 4))
        colour[:, 0] = np.linspace(0.2, base_colour[0], n)
        colour[:, 1] = np.linspace(0.2, base_colour[1], n)
        colour[:, 2] = np.linspace(0.5, base_colour[2], n)
        colour[:, 3] = np.linspace(0.0, alpha, n)
        return colour

    def get_colour_array(self, n, alpha, base_colour):
        mode = "trail" if self._trail_mode else "flat"
        colour_key = tuple(round(float(c), 6) for c in base_colour)
        key = (mode, n, round(float(alpha), 6), colour_key)
        cached = self._colour_cache.get(key)
        if cached is not None:
            return cached

        if self._trail_mode:
            colour = self.plot_trail(n, alpha, base_colour)
        else:
            colour = np.full((n, 4), (*base_colour, alpha))

        self._colour_cache[key] = colour

        return colour

    def refresh_colours(self):
        if not self._solutions:
            return
        for i, sol in enumerate(self._solutions):
            _, colour = self.get_traj_tail_data(i, sol)
            self._set_trajectory_data(i, colour=colour)

    def display_solutions(self, solutions, is_partial):
        if not is_partial:
            self._solutions = solutions

        self.sync_gl_items(len(solutions))

        for i, sol in enumerate(solutions):
            segment, colour = self.get_traj_tail_data(i, sol)
            self._set_trajectory_data(i, pos=segment, colour=colour)

    def clear_solutions(self):
        self._solutions = None
        self.sync_gl_items(0)

    def get_traj_tail_data(self, i, sol):
        if self._traj_tail_enabled:
            segment = sol[-self._traj_tail_length :]
        else:
            segment = sol

        segment = _decimate_for_display(segment, STATIC_RENDER_MAX_POINTS)

        base_colour, alpha = self.get_traj_colour_alpha(i)
        colour = self.get_colour_array(len(segment), alpha, base_colour)

        return segment, colour

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
        for i, sol in enumerate(self._solutions):
            segment, colour = self.get_traj_tail_data(i, sol)
            self._set_trajectory_data(i, pos=segment, colour=colour)

    def _set_trajectory_data(self, i, *, pos=None, colour=None):
        if i >= len(self._scatters):
            return

        line_mode = self._trajectory_line_mode(i)
        kwargs = {}
        if pos is not None:
            kwargs["pos"] = pos
        if colour is not None:
            kwargs["color"] = colour

        self._scatters[i].setData(**kwargs)
        self._scatters[i].setVisible(not line_mode)
        self._lines[i].setData(**kwargs)
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
        for i, sol in enumerate(self._solutions):
            if self._traj_tail_enabled:
                start = max(0, frame - self._traj_tail_length)
                segment = sol[start:frame]
            else:
                segment = sol[:frame]
            render_segment = _decimate_for_display(segment, ANIM_RENDER_MAX_POINTS)
            base_colour, alpha = self.get_traj_colour_alpha(i)
            colour = self.get_colour_array(len(render_segment), alpha, base_colour)
            if i < len(self._scatters):
                self._scatters[i].setData(pos=render_segment, color=colour)
                self._lines[i].setData(pos=render_segment, color=colour)
            if i < len(self._heads):
                self._heads[i].setData(pos=render_segment[-1:], color=colour[-1:])
            all_segments.append(segment)

        return all_segments
