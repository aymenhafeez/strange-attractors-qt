# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.style import PANEL_SURFACE, plot_colours
from ..view.camera_controller import CameraController
from ..view.grid_overlay import GridOverlay
from .docked_views import DockedViewManager
from .explorer import (
    PLOT_MODE_OVERLAY,
    PLOT_MODE_REPLACE,
    ExplorerControls,
    control_key,
    parse_mode,
    resolve,
)


def check_points(x, y=None, z=None):
    if y is None and z is None:
        points = np.asarray(x, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("Points must have shape (N, 3)")
    else:
        if y is None or z is None:
            raise ValueError("Must provide x, y and z")

        x_data = np.asarray(x, dtype=np.float64)
        y_data = np.asarray(y, dtype=np.float64)
        z_data = np.asarray(z, dtype=np.float64)

        if x_data.ndim != 1 or y_data.ndim != 1 or z_data.ndim != 1:
            raise ValueError("x, y and z must be one dimensional")
        if not (len(x_data) == len(y_data) == len(z_data)):
            raise ValueError("x, y and z must be the same length")

        points = np.column_stack([x_data, y_data, z_data])

    return points


def check_surface_grid(x, y=None, z=None):
    if y is None and z is None:
        z_grid = np.asarray(x)
        if z_grid.ndim != 2:
            raise ValueError("Surface z must be two dimensional")

        rows, columns = z_grid.shape
        y_grid, x_grid = np.mgrid[0:rows, 0:columns]
    else:
        if y is None or z is None:
            raise ValueError("Must provide x, y and z")

        x_data = np.asarray(x)
        y_data = np.asarray(y)
        z_grid = np.asarray(z)

        if z_grid.ndim != 2:
            raise ValueError("Surface z must be two dimensional")

        if x_data.ndim == 1 and y_data.ndim == 1:
            if len(x_data) != z_grid.shape[1]:
                raise ValueError("x length must match z columns")
            if len(y_data) != z_grid.shape[0]:
                raise ValueError("y length must match z rows")

            x_grid, y_grid = np.meshgrid(x_data, y_data)

        elif x_data.ndim == 2 and y_data.ndim == 2:
            if x_data.shape != z_grid.shape or y_data.shape != z_grid.shape:
                raise ValueError("x, y and z grids must have the same shape")

            x_grid = x_data
            y_grid = y_data

        else:
            raise ValueError("x and y must both be 1D or both be 2D")

    if z_grid.size == 0:
        raise ValueError("Surface grid can't be empty")

    points = np.column_stack([x_grid.ravel(), y_grid.ravel(), z_grid.ravel()])
    if not np.isfinite(points).all():
        raise ValueError("Surface grid can't contain non finite values")

    return x_grid, y_grid, z_grid, points


# GLSurfacePlotItem works cleanly with rectilinear x, y for surface3d
def rectilinear_surface_axes(x_grid, y_grid):
    x_axis = x_grid[0, :]
    y_axis = y_grid[:, 0]

    if not np.allclose(x_grid, x_axis):
        raise ValueError("surface3d requires a rectilinear x grid")
    if not np.allclose(y_grid, y_axis[:, np.newaxis]):
        raise ValueError("surface3d requires a rectilinear y grid")

    return x_axis, y_axis


def surface_wireframe_lines(x_grid, y_grid, z_grid):
    grid = np.dstack([x_grid, y_grid, z_grid])
    gap = np.full((1, 3), np.nan)
    rows = []
    for line in (*grid, *grid.transpose(1, 0, 2)):
        rows += [line, gap]

    return np.vstack(rows[:-1])


def normalise_colour(colour, n=None):
    if isinstance(colour, str):
        qcolour = QtGui.QColor(colour)
        if not qcolour.isValid():
            raise ValueError(f"Invalid colour {colour!r}")

        return qcolour.redF(), qcolour.greenF(), qcolour.blueF(), qcolour.alphaF()

    data = np.asarray(colour, dtype=np.float32)
    if data.shape == (3,):
        return (*data, 1.0)
    if data.shape == (4,):
        return tuple(data)
    if data.ndim != 2 or data.shape[1] not in {3, 4}:
        raise ValueError(
            "Colour must be a name, hex string, RGB(A) or an (N, 3)/(N, 4) array"
        )

    if n is None:
        raise TypeError("Colour must be a single colour")
    if len(data) != n:
        raise ValueError("Colour array must be the same length as points")
    if data.shape[1] == 3:
        data = np.column_stack([data, np.ones(len(data), dtype=np.float32)])

    return data


def normalise_size(size, n):
    if np.isscalar(size):
        return float(size)

    data = np.asarray(size, dtype=np.float64)
    if data.ndim != 1:
        raise ValueError("Size must be a number or 1D array")
    if len(data) != n:
        raise ValueError("Size array must be the same length as points")

    return data


class ConsoleTrace3D:
    def __init__(self, name, x, y, z, item, explorer, kind, colour=None, size=None):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.item = item
        self.kind = kind
        self.size = size
        self.colour = colour
        self.explorer = explorer

    def points(self):
        return check_points(resolve(self.x), resolve(self.y), resolve(self.z))

    def update(self):
        points = self.points()
        kwargs = {"pos": points}

        colour = self.colour_data(len(points))
        if colour is not None:
            kwargs["color"] = colour

        if self.kind == "scatter3d":
            size = self.size_data(len(points))
            if size is not None:
                kwargs["size"] = size

        self.item.setData(**kwargs)

    def remove(self):
        self.explorer.view.remove_item(self.item)

    def colour_data(self, n):
        if self.colour is None:
            return None

        return normalise_colour(resolve(self.colour), n)

    def size_data(self, n):
        if self.size is None:
            return None

        return normalise_size(resolve(self.size), n)


class ConsoleSurfaceTrace3D:
    def __init__(
        self, name, x, y, z, item, explorer, kind, colour=None, wireframe=False
    ):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.item = item
        self.explorer = explorer
        self.kind = kind
        self.colour = colour
        self.wireframe = wireframe

    def grid(self):
        return check_surface_grid(resolve(self.x), resolve(self.y), resolve(self.z))

    def points(self):
        return self.grid()[3]

    def update(self):
        x_grid, y_grid, z_grid, _points = self.grid()

        colour = self.colour_data()
        if self.wireframe:
            kwargs = {"pos": surface_wireframe_lines(x_grid, y_grid, z_grid)}
            if colour is not None:
                # getting passed to OpenGL so use 'color' for the internal arg and
                # colour for the user facing arg
                kwargs["color"] = colour
            self.item.setData(**kwargs)
            return

        x_axis, y_axis = rectilinear_surface_axes(x_grid, y_grid)
        kwargs = {"x": x_axis, "y": y_axis, "z": z_grid}

        if colour is not None:
            kwargs["color"] = colour

        self.item.setData(**kwargs)

    def colour_data(self):
        if self.colour is None:
            return None

        return normalise_colour(resolve(self.colour))

    def remove(self):
        self.explorer.view.remove_item(self.item)


class ConsoleView3D:
    def __init__(self, status_callback=None):
        self._manager = None
        self._items = []
        self._status_callback = status_callback

        self._point_sets = []

        self.host = QtWidgets.QWidget()
        self.host.setObjectName("panelSurface")
        self.host.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.host.setStyleSheet(PANEL_SURFACE)

        self.layout = QtWidgets.QVBoxLayout(self.host)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(0)

        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor(plot_colours()["gl_background"])
        self.camera_controller = CameraController(self.view)
        self.grid_overlay = GridOverlay(self.view)
        self.grid_overlay.build_grid()

        self.layout.addWidget(self.view, 1)

        self.param_widget = QtWidgets.QFrame()
        self.param_widget.setObjectName("ConsolePlotParams")
        self.param_widget.setVisible(False)

        self.param_layout = QtWidgets.QVBoxLayout(self.param_widget)
        self.param_layout.setContentsMargins(6, 5, 6, 6)
        self.param_layout.setSpacing(4)

        self.param_controls = QtWidgets.QFrame()
        self.param_controls.setObjectName("ConsolePlotParamControls")
        self.param_controls_layout = QtWidgets.QVBoxLayout(self.param_controls)
        self.param_controls_layout.setContentsMargins(5, 5, 5, 5)
        self.param_controls_layout.setSpacing(3)

        self.param_layout.addWidget(self.param_controls)

        self.explore = View3DExplorer(
            self,
            self.param_widget,
            self.param_controls_layout,
            status_callback=status_callback,
            parent=self.host,
        )

        self.layout.addWidget(self.param_widget)

    def __repr__(self):
        return "ConsoleView3D()"

    def clear(self):
        self.explore.clear_traces()
        self.clear_items()

    def clear_items(self):
        for item in list(self._items):
            self.remove_item(item)

    def remove_item(self, item):
        if item in self._items:
            index = self._items.index(item)
            self.view.removeItem(item)
            self._items.pop(index)
            self._point_sets.pop(index)

    def _add(self, item, points):
        self.view.addItem(item)
        self._items.append(item)
        self._point_sets.append(points)
        self.auto_adjust_grid()
        self.camera_controller.fit_camera_to_solutions([points])

        return item

    def point_sets(self):
        trace_items = set()
        point_sets = []

        for trace in self.explore._traces.values():
            trace_items.add(trace.item)
            point_sets.append(trace.points())

        for item, points in zip(self._items, self._point_sets):
            if item not in trace_items:
                point_sets.append(points)

        return point_sets

    def fit(self):
        sets = self.point_sets()
        self.grid_overlay.auto_adjust_grid(sets)
        self.camera_controller.fit_camera_to_solutions(sets)
        return self

    def auto_adjust_grid(self):
        self.grid_overlay.auto_adjust_grid(self.point_sets())
        return self

    def reset_camera(self):
        self.view.setCameraPosition(distance=10, elevation=20, azimuth=45)
        return self

    def orbit(self, enabled):
        self.camera_controller.set_orbit_mode(enabled)
        return self

    def orbit_speed(self, speed):
        self.camera_controller.set_orbit_speed(speed)
        return self

    def grid(self, visible=True):
        self.grid_overlay.set_grid_visible(visible)
        return self

    def grid_visible(self):
        return self.grid_overlay._grid_visible

    def line3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode=PLOT_MODE_REPLACE,
        colour=(1.0, 1.0, 1.0, 1.0),
        width=1.0,
        antialias=True,
    ):
        points = check_points(x, y, z)

        if parse_mode(mode) == PLOT_MODE_REPLACE:
            self.clear()

        colour = normalise_colour(colour, len(points))

        item = gl.GLLinePlotItem(
            pos=points,
            color=colour,
            width=width,
            antialias=antialias,
            mode="line_strip",
        )

        return self._add(item, points)

    def scatter3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode=PLOT_MODE_REPLACE,
        colour=(1.0, 1.0, 1.0, 1.0),
        size=5.0,
        px_mode=True,
    ):
        points = check_points(x, y, z)

        if parse_mode(mode) == PLOT_MODE_REPLACE:
            self.clear()

        colour = normalise_colour(colour, len(points))
        size = normalise_size(size, len(points))

        item = gl.GLScatterPlotItem(
            pos=points,
            color=colour,
            size=size,
            pxMode=px_mode,
        )
        item.setGLOptions("additive" if plot_colours()["is_dark"] else "translucent")

        return self._add(item, points)

    def surface3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode=PLOT_MODE_REPLACE,
        colour=(0.2, 0.8, 1.0, 1.0),
        shader="shaded",
        smooth=True,
        show_grid=False,
    ):
        x_grid, y_grid, z_grid, points = check_surface_grid(x, y, z)
        x_axis, y_axis = rectilinear_surface_axes(x_grid, y_grid)

        if parse_mode(mode) == PLOT_MODE_REPLACE:
            self.clear()

        colour = normalise_colour(colour)

        item = gl.GLSurfacePlotItem(
            x=x_axis,
            y=y_axis,
            z=z_grid,
            color=colour,
            shader=shader,
            smooth=smooth,
            showGrid=show_grid,
        )

        return self._add(item, points)

    def wireframe3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode=PLOT_MODE_REPLACE,
        colour=(0.8, 0.8, 0.8, 1.0),
        width=1.0,
        antialias=True,
    ):
        x_grid, y_grid, z_grid, points = check_surface_grid(x, y, z)

        if parse_mode(mode) == PLOT_MODE_REPLACE:
            self.clear()

        colour = normalise_colour(colour)

        item = gl.GLLinePlotItem(
            pos=surface_wireframe_lines(x_grid, y_grid, z_grid),
            color=colour,
            width=width,
            antialias=antialias,
            mode="line_strip",
        )

        return self._add(item, points)

    def apply_theme(self):
        colours = plot_colours()
        gl_options = "additive" if colours["is_dark"] else "translucent"

        self.view.setBackgroundColor(colours["gl_background"])
        self.grid_overlay.apply_theme()

        for item in self._items:
            item.setGLOptions(gl_options)


class ConsoleView3DManager(DockedViewManager):
    kind = "view"
    name_prefix = "3D View"
    dock_prefix = "view3d"
    active_kind = "view3d"

    def set_status_callback(self, callback):
        super().set_status_callback(callback)
        for view in self._views.values():
            view.explore.status_callback = callback

    # convenience so views3d.line3d/scatter3d works
    def line3d(self, *args, **kwargs):
        return self.current.line3d(*args, **kwargs)

    def scatter3d(self, *args, **kwargs):
        return self.current.scatter3d(*args, **kwargs)

    def surface3d(self, *args, **kwargs):
        return self.current.surface3d(*args, **kwargs)

    def wireframe3d(self, *args, **kwargs):
        return self.current.wireframe3d(*args, **kwargs)

    def fit(self):
        return self.current.fit()

    def reset_camera(self):
        return self.current.reset_camera()

    def orbit(self, enabled):
        return self.current.orbit(enabled)

    def orbit_speed(self, speed):
        return self.current.orbit_speed(speed)

    def grid(self, visible=True):
        return self.current.grid(visible)

    def grid_visible(self):
        return self.current.grid_visible()

    def apply_theme(self):
        for view in self._views.values():
            view.apply_theme()

    def _make_view(self):
        return ConsoleView3D()

    def _connect_view(self, view):
        view._manager = self
        view.explore.status_callback = self._status_callback


class View3DExplorer(ExplorerControls):
    def __init__(
        self, view, param_widget, param_layout, status_callback=None, parent=None
    ):
        super().__init__(param_widget, param_layout, status_callback, parent)
        self.view = view

    def _begin_trace(self, name, mode):
        mode = parse_mode(mode)
        key = control_key(name, "Trace")
        if mode == PLOT_MODE_REPLACE:
            self.clear_traces()
            self.view.clear_items()

        # drop the old trace before plotting so point_sets() doesn't evaluate it
        return self._new_trace_key(key)

    def _add_trace3d(self, name, x, y, z, mode, plotter, kind, **kwargs):
        key = self._begin_trace(name, mode)
        colour = kwargs.get("colour")
        size = kwargs.get("size")
        for option in ("colour", "size"):
            if option in kwargs:
                kwargs[option] = resolve(kwargs[option])

        points = check_points(resolve(x), resolve(y), resolve(z))
        item = plotter(points, mode=PLOT_MODE_OVERLAY, **kwargs)
        trace = ConsoleTrace3D(
            key, x, y, z, item, self, kind=kind, colour=colour, size=size
        )

        return self._store_trace(key, trace)

    def _add_surface_trace3d(
        self, name, x, y, z, mode, plotter, kind, wireframe, **kwargs
    ):
        key = self._begin_trace(name, mode)
        colour = kwargs.get("colour")
        if "colour" in kwargs:
            kwargs["colour"] = resolve(colour)

        item = plotter(
            resolve(x), resolve(y), resolve(z), mode=PLOT_MODE_OVERLAY, **kwargs
        )
        trace = ConsoleSurfaceTrace3D(
            key, x, y, z, item, self, kind=kind, colour=colour, wireframe=wireframe
        )

        return self._store_trace(key, trace)

    def line3d(self, name, x, y=None, z=None, *, mode=PLOT_MODE_REPLACE, **kwargs):
        return self._add_trace3d(
            name, x, y, z, mode=mode, plotter=self.view.line3d, kind="line3d", **kwargs
        )

    def scatter3d(self, name, x, y=None, z=None, *, mode=PLOT_MODE_REPLACE, **kwargs):
        return self._add_trace3d(
            name,
            x,
            y,
            z,
            mode=mode,
            plotter=self.view.scatter3d,
            kind="scatter3d",
            **kwargs,
        )

    def surface3d(self, name, x, y=None, z=None, *, mode=PLOT_MODE_REPLACE, **kwargs):
        return self._add_surface_trace3d(
            name,
            x,
            y,
            z,
            mode=mode,
            plotter=self.view.surface3d,
            kind="surface3d",
            wireframe=False,
            **kwargs,
        )

    def wireframe3d(self, name, x, y=None, z=None, *, mode=PLOT_MODE_REPLACE, **kwargs):
        return self._add_surface_trace3d(
            name,
            x,
            y,
            z,
            mode=mode,
            plotter=self.view.wireframe3d,
            kind="wireframe3d",
            wireframe=True,
            **kwargs,
        )

    def refresh(self):
        updated = super().refresh()
        if updated:
            self.view.auto_adjust_grid()

        return updated

    def traces(self):
        return {
            name: {
                "name": trace.name,
                "kind": trace.kind,
            }
            for name, trace in self._traces.items()
        }
