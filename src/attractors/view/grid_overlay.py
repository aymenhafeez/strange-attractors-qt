import numpy as np
import pyqtgraph.opengl as gl

from ..ui.style import plot_colours

DEFAULT_GRID_HALF_SIZE = 50.0
DEFAULT_AXIS_LIMIT = 1.0
AXIS_PADDING_FACTOR = 0.5
MIN_AXIS_SPAN = 1.0
GRID_CHANGE_THRESHOLD = 0.02


class GridOverlay:
    def __init__(self, view):
        self.view = view
        self._grid_visible = True
        self.grid_items = []
        self._grid_axis_item = None
        self._bounds = self._default_bounds()

        self._poincare_axis = None
        self._poincare_value = 0.0
        self._poincare_plane_items = []

    @property
    def grid_half_size(self):
        # Compatibility for existing callers.
        spans = [high - low for low, high in self._bounds.values()]
        return max(spans) * 0.5

    def build_grid(self, bounds=None):
        if bounds is None:
            bounds = self._default_bounds()
        elif np.isscalar(bounds):
            bounds = self._bounds_from_half_size(bounds)

        self._bounds = self._normalise_bounds(bounds)

        if self._grid_axis_item is None:
            self._grid_axis_item = gl.GLGridAxisItem()
            self.view.addItem(self._grid_axis_item)
            self.grid_items = [self._grid_axis_item]

        coords = {
            axis: self._nice_ticks(low, high)
            for axis, (low, high) in self._bounds.items()
        }
        coords_labels = {
            axis: [self._format_tick(value) for value in values]
            for axis, values in coords.items()
        }

        self._grid_axis_item.setData(
            coords=coords,
            coords_labels=coords_labels,
            limits=self._bounds,
            face_color=plot_colours()["gl_grid_face"],
            line_color=plot_colours()["gl_grid_line"],
            label_color=plot_colours()["gl_axis_label"],
            line_width=1.0,
            line_antialias=True,
            tick_offset_factor=0.015,
        )
        self._grid_axis_item.setVisible(self._grid_visible)

        if self._poincare_axis is not None:
            self._update_poincare_plane()

    def set_grid_visible(self, visible):
        self._grid_visible = visible
        for item in self.grid_items:
            item.setVisible(visible)

    def set_poincare_plane(self, axis, value):
        self._poincare_axis = axis
        self._poincare_value = value
        self._update_poincare_plane()

    def remove_poincare_plane(self):
        self._poincare_axis = None
        for item in self._poincare_plane_items:
            self.view.removeItem(item)
        self._poincare_plane_items.clear()

    def auto_adjust_grid(self, solutions):
        if not solutions:
            return

        points = np.concatenate(solutions, axis=0)
        if points.size == 0:
            return

        finite_points = points[np.isfinite(points).all(axis=1)]
        if len(finite_points) == 0:
            return

        mins = finite_points.min(axis=0)
        maxs = finite_points.max(axis=0)
        bounds = self._bounds_from_extents(mins, maxs)

        if self._bounds_changed(bounds):
            self.build_grid(bounds)

    def _update_poincare_plane(self):
        for item in self._poincare_plane_items:
            self.view.removeItem(item)
        self._poincare_plane_items.clear()

        if self._poincare_axis is None:
            return

        axis = str(self._poincare_axis).lower()
        value = float(self._poincare_value)

        x_low, x_high = self._bounds["x"]
        y_low, y_high = self._bounds["y"]
        z_low, z_high = self._bounds["z"]

        if axis == "x":
            verts = np.array(
                [
                    [value, y_low, z_low],
                    [value, y_high, z_low],
                    [value, y_high, z_high],
                    [value, y_low, z_high],
                ],
                dtype=np.float64,
            )
        elif axis == "y":
            verts = np.array(
                [
                    [x_low, value, z_low],
                    [x_high, value, z_low],
                    [x_high, value, z_high],
                    [x_low, value, z_high],
                ],
                dtype=np.float64,
            )
        else:
            verts = np.array(
                [
                    [x_low, y_low, value],
                    [x_high, y_low, value],
                    [x_high, y_high, value],
                    [x_low, y_high, value],
                ],
                dtype=np.float64,
            )

        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
        vertex_colours = np.full((4, 4), [1.0, 0.3, 0.3, 0.35], dtype=np.float32)

        mesh = gl.GLMeshItem(
            vertexes=verts,
            faces=faces,
            vertexColors=vertex_colours,
            smooth=False,
            glOptions="translucent",
        )
        self.view.addItem(mesh)
        self._poincare_plane_items.append(mesh)

        border = gl.GLLinePlotItem(
            pos=np.vstack([verts, verts[0]]),
            color=(1.0, 0.3, 0.3, 0.7),
            width=1.5,
            glOptions="translucent",
        )
        self.view.addItem(border)
        self._poincare_plane_items.append(border)

    def _default_bounds(self):
        return {
            "x": (-DEFAULT_AXIS_LIMIT, DEFAULT_AXIS_LIMIT),
            "y": (-DEFAULT_AXIS_LIMIT, DEFAULT_AXIS_LIMIT),
            "z": (-DEFAULT_AXIS_LIMIT, DEFAULT_AXIS_LIMIT),
        }

    def _bounds_from_half_size(self, half_size):
        half_size = float(half_size)
        if not np.isfinite(half_size) or half_size <= 0:
            half_size = DEFAULT_AXIS_LIMIT

        return {
            "x": (-half_size, half_size),
            "y": (-half_size, half_size),
            "z": (-half_size, half_size),
        }

    def _normalise_bounds(self, bounds):
        normalised = {}

        for axis in "xyz":
            low, high = bounds[axis]
            low = float(low)
            high = float(high)

            if not np.isfinite(low) or not np.isfinite(high):
                low, high = -DEFAULT_AXIS_LIMIT, DEFAULT_AXIS_LIMIT

            if low > high:
                low, high = high, low

            if low == high:
                half_span = MIN_AXIS_SPAN * 0.5
                low -= half_span
                high += half_span

            normalised[axis] = (low, high)

        return normalised

    def _bounds_from_extents(self, mins, maxs):
        bounds = {}

        for axis, low, high in zip("xyz", mins, maxs):
            low = float(low)
            high = float(high)
            span = max(high - low, MIN_AXIS_SPAN)
            centre = 0.5 * (low + high)
            half_span = 0.5 * span * (1.0 + AXIS_PADDING_FACTOR)

            bounds[axis] = (
                centre - half_span,
                centre + half_span,
            )

        return bounds

    def _bounds_changed(self, bounds):
        bounds = self._normalise_bounds(bounds)

        for axis in "xyz":
            old_low, old_high = self._bounds[axis]
            new_low, new_high = bounds[axis]
            old_span = max(old_high - old_low, MIN_AXIS_SPAN)

            if abs(new_low - old_low) / old_span > GRID_CHANGE_THRESHOLD:
                return True
            if abs(new_high - old_high) / old_span > GRID_CHANGE_THRESHOLD:
                return True

        return False

    def _nice_ticks(self, low, high, target_count=5):
        span = high - low
        if span <= 0:
            return np.array([low], dtype=np.float64)

        raw_step = span / max(target_count - 1, 1)
        magnitude = 10 ** np.floor(np.log10(raw_step))
        residual = raw_step / magnitude

        if residual <= 1:
            step = magnitude
        elif residual <= 2:
            step = 2 * magnitude
        elif residual <= 5:
            step = 5 * magnitude
        else:
            step = 10 * magnitude

        start = np.ceil(low / step) * step
        stop = np.floor(high / step) * step
        ticks = np.arange(start, stop + step * 0.5, step)

        if len(ticks) < 2:
            ticks = np.linspace(low, high, target_count)

        return ticks.astype(np.float64)

    def _format_tick(self, value):
        return f"{value:g}"

    def apply_theme(self):
        if self._grid_axis_item is not None:
            self._grid_axis_item.setData(
                face_color=plot_colours()["gl_grid_face"],
                line_color=plot_colours()["gl_grid_line"],
                label_color=plot_colours()["gl_axis_label"],
            )
