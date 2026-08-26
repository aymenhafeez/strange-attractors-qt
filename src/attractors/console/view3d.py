import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.docking import AreaBoundDock as Dock
from ..ui.style import CONSOLE_PLOT_PARAMS
from ..view.camera_controller import CameraController
from ..view.grid_overlay import GridOverlay
from .animation import ConsoleAnimation, ConsoleAnimationWidget
from .explorer import ConsoleParam


def check_points(x, y=None, z=None, *, name="points"):
    if y is None and z is None:
        points = np.asarray(x, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError(f"{name} must have shape (N, 3)")
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

    # removing this check for now to allow initialising plots with empty arrays
    # for 3D animations to keep things consisten with 2D animations
    # if len(points) == 0:
    #     raise ValueError(f"{name} cannot be empty")

    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} can't contain non finite values")

    return points


def check_surface_grid(x, y=None, z=None, *, name="surface"):
    if y is None and z is None:
        z_grid = np.asarray(x)
        if z_grid.ndim != 2:
            raise ValueError(f"{name} z must be two dimensional")

        rows, columns = z_grid.shape
        y_grid, x_grid = np.mgrid[0:rows, 0:columns]
    else:
        if y is None or z is None:
            raise ValueError("Must provide x, y and z")

        x_data = np.asarray(x)
        y_data = np.asarray(y)
        z_grid = np.asarray(z)

        if z_grid.ndim != 2:
            raise ValueError(f"{name} z must be two dimensional")

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
        raise ValueError(f"{name} grid can't be empty")

    if not (
        np.all(np.isfinite(x_grid))
        and np.all(np.isfinite(y_grid))
        and np.all(np.isfinite(z_grid))
    ):
        raise ValueError(f"{name} grid can't contain non finite values")

    points = np.column_stack([x_grid.ravel(), y_grid.ravel(), z_grid.ravel()])

    return x_grid, y_grid, z_grid, points


# GLSurfacePlotItem works cleanly with rectilinear x, y for surface3d
def rectilinear_surface_axes(x_grid, y_grid):
    x_axis = x_grid[0, :]
    y_axis = y_grid[:, 0]

    expected_x = np.tile(x_axis, (x_grid.shape[0], 1))
    expected_y = np.tile(y_axis[:, np.newaxis], (1, y_grid.shape[1]))

    if not np.allclose(x_grid, expected_x):
        raise ValueError("surface3d requires a rectilinear x grid")
    if not np.allclose(y_grid, expected_y):
        raise ValueError("surface3d requires a rectilinear y grid")

    return x_axis, y_axis


def surface_wireframe_lines(x_grid, y_grid, z_grid):
    rows = []

    for row in range(z_grid.shape[0]):
        rows.append(np.column_stack([x_grid[row], y_grid[row], z_grid[row]]))
        rows.append(np.full((1, 3), np.nan))

    for column in range(z_grid.shape[1]):
        rows.append(
            np.column_stack([x_grid[:, column], y_grid[:, column], z_grid[:, column]])
        )
        rows.append(np.full((1, 3), np.nan))

    if not rows:
        return np.empty((0, 3))

    return np.vstack(rows[:-1])


def normalise_colour(colour):
    if isinstance(colour, str):
        qcolour = QtGui.QColor(colour)
        if not qcolour.isValid():
            raise ValueError(f"Invalid colour {colour!r}")

        return qcolour.redF(), qcolour.greenF(), qcolour.blueF(), qcolour.alphaF()

    data = np.asarray(colour, dtype=np.float32)

    if data.shape == (3,):
        return (data[0], data[1], data[2], 1.0)
    if data.shape == (4,):
        return tuple(v for v in data)

    # per point rgb(a)
    if data.ndim == 2 and data.shape[1] in {3, 4}:
        if data.shape[1] == 3:
            alpha = np.ones((len(data), 1), dtype=np.float32)
            data = np.column_stack([data, alpha])

        return data

    raise ValueError(
        "Colour must be a name, hex string, RGB(A) or an (N, 3)/(N, 4) array"
    )


def normalise_size(size, n):
    if np.isscalar(size):
        return float(size)

    data = np.asarray(size, dtype=np.float64)
    if data.ndim != 1:
        raise ValueError("Size must be a number or 1D array")
    if len(data) != n:
        raise ValueError("Size array must be the same length as points")
    if not np.all(np.isfinite(data)):
        raise ValueError("Size can't contain non finite values")

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
        x_data = self.x() if callable(self.x) else self.x

        if self.y is None and self.z is None:
            return check_points(x_data)

        y_data = self.y() if callable(self.y) else self.y
        z_data = self.z() if callable(self.z) else self.z

        return check_points(x_data, y_data, z_data)

    def update(self):
        points = self.points()
        kwargs = {"pos": points}

        colour = self.colour_data(len(points))
        if colour is not None:
            # arg getting passed to GLLinePlotItem and GLScatterPlotItem which expect 'color' not 'colour'
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

        colour_data = self.colour() if callable(self.colour) else self.colour
        colour = normalise_colour(colour_data)

        if isinstance(colour, np.ndarray) and len(colour) != n:
            raise ValueError("Colour array must be the same length as points")

        return colour

    def size_data(self, n):
        if self.size is None:
            return None

        size_data = self.size() if callable(self.size) else self.size

        return normalise_size(size_data, n)


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
        x_data = self.x() if callable(self.x) else self.x

        if self.y is None and self.z is None:
            return check_surface_grid(x_data)

        y_data = self.y() if callable(self.y) else self.y
        z_data = self.z() if callable(self.z) else self.z

        return check_surface_grid(x_data, y_data, z_data)

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
            return

        colour_data = self.colour() if callable(self.colour) else self.colour
        colour = normalise_colour(colour_data)

        if isinstance(colour, np.ndarray):
            raise TypeError(f"{self.kind} colour must be a single colour")

        return colour

    def remove(self):
        self.explorer.view.remove_item(self.item)


class ConsoleView3D:
    def __init__(self, status_callback=None):
        self._manager = None
        self._items = []
        self._status_callback = status_callback

        self._point_sets = []

        self.host = QtWidgets.QWidget()
        # layout reserved name in Qt so using v_layout instead
        self.v_layout = QtWidgets.QVBoxLayout(self.host)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)

        self.view = gl.GLViewWidget()
        self.camera_controller = CameraController(self.view)
        self.grid_overlay = GridOverlay(self.view)
        self.grid_overlay.build_grid()

        self.v_layout.addWidget(self.view, 1)

        self.param_widget = QtWidgets.QFrame()
        self.param_widget.setObjectName("ConsolePlotParams")
        self.param_widget.setVisible(False)
        self.param_widget.setStyleSheet(CONSOLE_PLOT_PARAMS)

        self.param_layout = QtWidgets.QVBoxLayout(self.param_widget)
        self.param_layout.setContentsMargins(6, 5, 6, 6)
        self.param_layout.setSpacing(4)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(4)

        self.param_title = QtWidgets.QLabel("Parameters")
        self.param_title.setObjectName("ConsolePlotParamTitle")
        header_layout.addWidget(self.param_title)
        header_layout.addStretch(1)

        self.param_controls = QtWidgets.QFrame()
        self.param_controls.setObjectName("ConsolePlotParamControls")
        self.param_controls_layout = QtWidgets.QVBoxLayout(self.param_controls)
        self.param_controls_layout.setContentsMargins(5, 5, 5, 5)
        self.param_controls_layout.setSpacing(3)

        # self.param_layout.addWidget(header)
        self.param_layout.addWidget(self.param_controls)

        self.explore = View3DExplorer(
            self,
            self.param_widget,
            self.param_controls_layout,
            status_callback=status_callback,
            parent=self.host,
        )

        self.v_layout.addWidget(self.param_widget)

    def __repr__(self):
        return "ConsoleView3D()"

    def clear(self):
        if hasattr(self, "explore"):
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

    def point_sets(self):
        trace_items = set()
        point_sets = []

        if hasattr(self, "explore"):
            for trace in self.explore._traces.values():
                trace_items.add(trace.item)
                point_sets.append(trace.points())

        for item, points in zip(self._items, self._point_sets):
            if item not in trace_items:
                point_sets.append(points)

        return point_sets

    def fit(self):
        self.grid_overlay.auto_adjust_grid(self.point_sets())
        self.camera_controller.fit_camera_to_solutions(self.point_sets())
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

    def clear_for_mode(self, mode):
        mode = str(mode).strip().lower()
        if mode == "replace":
            return True
        if mode == "overlay":
            return False

        raise ValueError("Mode must be 'replace' or 'overlay'")

    def line3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode="replace",
        colour=(1.0, 1.0, 1.0, 1.0),
        width=1.0,
        antialias=True,
    ):
        points = check_points(x, y, z)

        if self.clear_for_mode(mode):
            self.clear()

        colour = normalise_colour(colour)
        if isinstance(colour, np.ndarray) and len(colour) != len(points):
            raise ValueError("Colour array must be the same length as points")

        item = gl.GLLinePlotItem(
            pos=points,
            color=colour,
            width=width,
            antialias=antialias,
            mode="line_strip",
        )

        self.view.addItem(item)
        self._items.append(item)
        self._point_sets.append(points)
        self.auto_adjust_grid()
        self.camera_controller.fit_camera_to_solutions([points])

        return item

    def scatter3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode="replace",
        colour=(1.0, 1.0, 1.0, 1.0),
        size=5.0,
        px_mode=True,
    ):
        points = check_points(x, y, z)

        if self.clear_for_mode(mode):
            self.clear()

        colour = normalise_colour(colour)
        if isinstance(colour, np.ndarray) and len(colour) != len(points):
            raise ValueError("Colour array must be the same length as points")

        size = normalise_size(size, len(points))

        item = gl.GLScatterPlotItem(
            pos=points,
            color=colour,
            size=size,
            pxMode=px_mode,
        )

        item.setGLOptions("additive")
        self.view.addItem(item)
        self._items.append(item)
        self._point_sets.append(points)
        self.auto_adjust_grid()
        self.camera_controller.fit_camera_to_solutions([points])

        return item

    def surface3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode="replace",
        colour=(0.2, 0.8, 1.0, 1.0),
        shader="shaded",
        smooth=True,
        show_grid=False,
    ):
        x_grid, y_grid, z_grid, points = check_surface_grid(x, y, z)
        x_axis, y_axis = rectilinear_surface_axes(x_grid, y_grid)

        if self.clear_for_mode(mode):
            self.clear()

        colour = normalise_colour(colour)
        if isinstance(colour, np.ndarray):
            raise TypeError("surface3d colour must be a single colour")

        item = gl.GLSurfacePlotItem(
            x=x_axis,
            y=y_axis,
            z=z_grid,
            color=colour,
            shader=shader,
            smooth=smooth,
            showGrid=show_grid,
        )

        self.view.addItem(item)
        self._items.append(item)
        self._point_sets.append(points)
        self.auto_adjust_grid()
        self.camera_controller.fit_camera_to_solutions([points])

        return item

    def wireframe3d(
        self,
        x,
        y=None,
        z=None,
        *,
        mode="replace",
        colour=(0.8, 0.8, 0.8, 1.0),
        width=1.0,
        antialias=True,
    ):
        x_grid, y_grid, z_grid, points = check_surface_grid(x, y, z)

        if self.clear_for_mode(mode):
            self.clear()

        colour = normalise_colour(colour)
        if isinstance(colour, np.ndarray):
            raise TypeError("wireframe3d colour must be a single colour")

        item = gl.GLLinePlotItem(
            pos=surface_wireframe_lines(x_grid, y_grid, z_grid),
            color=colour,
            width=width,
            antialias=antialias,
            mode="line_strip",
        )

        self.view.addItem(item)
        self._items.append(item)
        self._point_sets.append(points)
        self.auto_adjust_grid()
        self.camera_controller.fit_camera_to_solutions([points])

        return item


# adapting this from ConsolePlotManager, will need to generalise to 3D
class ConsoleView3DManager(QtCore.QObject):
    views_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    view_removed = QtCore.pyqtSignal(str, object)
    view_cleared = QtCore.pyqtSignal(str, object)

    def __init__(
        self,
        dock_area,
        default_name,
        default_view,
        default_dock,
        status_callback=None,
        active_callback=None,
    ):
        super().__init__(dock_area)
        self._dock_area = dock_area
        self._views = {default_name: default_view}
        self._docks = {default_name: default_dock}
        self._default_name = default_name
        self._current_name = default_name
        self._status_callback = status_callback
        self._active_callback = active_callback
        default_view._manager = self

    @property
    def current(self):
        return self._views[self._current_name]

    @property
    def current_name(self):
        return self._current_name

    def names(self):
        return list(self._views)

    def get(self, name, *, activate=True):
        key = self._view_name(name)
        try:
            view = self._views[key]
        except KeyError as exc:
            raise KeyError(f"No console view named {key!r}") from exc

        if activate:
            self._mark_active()
            self._set_current_name(key)
            dock = self._docks[key]
            self._raise_dock(dock)

        return view

    def rename(self, old_name, new_name):
        old_key = self._view_name(old_name)
        new_key = self._view_name(new_name)
        if old_key not in self._views:
            raise KeyError(f"No console view named {old_key!r}")
        if new_key != old_key and new_key in self._views:
            raise ValueError(f"Console view {new_key!r} already exists")

        if new_key == old_key:
            self._set_current_name(new_key)
            return self._views[new_key]

        self._mark_active()

        view = self._views.pop(old_key)
        dock = self._docks.pop(old_key)
        self._views[new_key] = view
        self._docks[new_key] = dock

        if old_key == self._default_name:
            self._default_name = new_key
        if old_key == self._current_name:
            self._current_name = new_key

        dock.setTitle(new_key)
        self.views_changed.emit()
        self.current_changed.emit(self._current_name)

        return view

    def new(self, name=None, *, activate=True):
        key = self._next_name() if name is None else self._view_name(name)
        if key in self._views:
            return self.get(key, activate=activate)

        view = ConsoleView3D(status_callback=self._status_callback)
        # i can't remember why this is needed
        view._manager = self
        dock = Dock(key, size=(10, 6), closable=True)
        dock.addWidget(view.host)

        dock.activated.connect(lambda view_name=key: self.activate(view_name))
        dock.sigClosed.connect(self._forget_dock)

        self._dock_area.addDock(
            dock,
            position="above",
            relativeTo=self._docks[self._default_name],
        )
        self._views[key] = view
        self._docks[key] = dock
        if activate:
            self._mark_active()
            self._set_current_name(key)
            dock.raiseDock()
        self.views_changed.emit()

        return view

    def _forget_dock(self, dock):
        for name, known_dock in self._docks.items():
            if known_dock is dock:
                self._forget(name)
                return

    def close(self, name=None):
        key = self._current_name if name is None else self._view_name(name)
        if key == self._default_name:
            view = self._views[key]
            view.clear()
            self.view_cleared.emit(key, view)
            self._set_current_name(key)

            return

        dock = self._docks.get(key)
        if dock is not None and dock.container() is not None:
            # closing the dock triggers sigClosed, which calls _forget itself
            dock.close()
        else:
            self._forget(key)

    def clear_all(self):
        for name, view in self._views.items():
            view.clear()
            self.view_cleared.emit(name, view)

    def clear(self):
        view = self.current
        view.clear()
        self.view_cleared.emit(self._current_name, view)

    # convenience, so views3d.line/scatter3d(points) works
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

    def _raise_dock(self, dock):
        container = dock.container()
        raise_dock = getattr(container, "raiseDock", None)
        if raise_dock is not None:
            raise_dock(dock)

    def _set_current_name(self, key):
        if self._current_name == key:
            return

        self._current_name = key
        self.current_changed.emit(key)

    def activate(self, name):
        key = self._view_name(name)
        if key not in self._views:
            return

        self._set_current_name(key)
        self._mark_active()

    def _mark_active(self):
        if self._active_callback is not None:
            self._active_callback("view3d")

    def _forget(self, name):
        if name == self._default_name:
            return
        if name not in self._views:
            return

        view = self._views.pop(name)
        self._docks.pop(name, None)
        if self._current_name == name:
            self._set_current_name(self._default_name)

        self.view_removed.emit(name, view)
        self.views_changed.emit()

    def _next_name(self):
        index = 2
        while True:
            name = f"3D View {index}"
            if name not in self._views:
                return name
            index += 1

    def _view_name(self, name):
        key = str(name).strip()
        if not key:
            raise ValueError("View name cannot be empty")

        return key

    def set_status_callback(self, callback):
        self._status_callback = callback
        for view in self._views.values():
            view._status_callback = callback
            view.explore.status_callback = callback


class View3DExplorer(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(
        self, view, param_widget, param_layout, status_callback=None, parent=None
    ):
        super().__init__(parent)
        self.view = view
        self.param_widget = param_widget
        self.param_layout = param_layout
        self.status_callback = status_callback
        self._params = {}
        self._traces = {}
        self._animations = {}

    def _trace_points(self, x, y=None, z=None):
        x_data = x() if callable(x) else x

        if y is None and z is None:
            return check_points(x_data)

        y_data = y() if callable(y) else y
        z_data = z() if callable(z) else z

        return check_points(x_data, y_data, z_data)

    def slider(self, name, value=0.0, start=0.0, end=1.0, step=0.01):
        key = str(name).strip()
        if not key:
            raise ValueError("Slider key cannot be empty")

        old = self._params.pop(key, None)
        if old is not None:
            self.param_layout.removeWidget(old.widget)
            old.widget.deleteLater()

        param = ConsoleParam(key, value, start, end, step, parent=self)
        param.changed.connect(self.refresh)
        self._params[key] = param
        self.param_layout.addWidget(param.widget)
        self.param_widget.setVisible(True)
        self.changed.emit()

        return param

    def animation(
        self,
        name,
        callback,
        *,
        interval=16,
        dt=None,
        frames=None,
        loop=False,
        start=False,
    ):
        key = str(name).strip()
        if not key:
            raise ValueError("Animation name can't be empty")

        old = self._animations.pop(key, None)
        if old is not None:
            old.pause()
            self.param_layout.removeWidget(old.widget)
            old.widget.deleteLater()

        animation = ConsoleAnimation(
            key,
            callback,
            interval=interval,
            dt=dt,
            frames=frames,
            loop=loop,
            status_callback=self.status_callback,
            parent=self,
        )
        widget = ConsoleAnimationWidget(animation)
        animation.widget = widget

        self._animations[key] = animation
        self.param_layout.addWidget(widget)
        self.param_widget.setVisible(True)
        self.changed.emit()

        if start:
            animation.play()

        return animation

    def animations(self):
        return {
            name: {
                "name": animation.name,
                "interval": animation.interval,
                "frame": animation.frame,
                "active": animation.is_active(),
            }
            for name, animation in self._animations.items()
        }

    def int_slider(self, name, value=0, start=0, end=100, step=1):
        return self.slider(name, int(value), int(start), int(end), int(step))

    def _add_trace3d(self, name, x, y, z, mode, plotter, kind, **kwargs):
        key = str(name).strip()
        if not key:
            raise ValueError("Trace name cannot be empty")

        # clear registered traces if mode is replace before adding a new one
        mode = mode.strip().lower()
        plot_mode = mode
        if mode == "replace":
            self.clear_traces()
            self.view.clear_items()
            plot_mode = "overlay"
        elif mode != "overlay":
            raise ValueError("Mode must be 'replace' or 'overlay'")

        old = self._traces.pop(key, None)
        if old is not None:
            old.remove()

        # user facing arg so use 'colour' here
        colour = kwargs.get("colour")
        if callable(colour):
            kwargs = kwargs.copy()
            kwargs["colour"] = colour()

        size = kwargs.get("size")
        if callable(size):
            kwargs = kwargs.copy()
            kwargs["size"] = size()

        points = self._trace_points(x, y, z)
        item = plotter(points, mode=plot_mode, **kwargs)
        trace = ConsoleTrace3D(
            key, x, y, z, item, self, kind=kind, colour=colour, size=size
        )
        self._traces[key] = trace
        self.changed.emit()

        return trace

    def _add_surface_trace3d(
        self, name, x, y, z, mode, plotter, kind, wireframe, **kwargs
    ):
        key = name.strip()
        if not key:
            raise ValueError("Trace name can't be empty")

        mode = mode.strip().lower()
        if mode == "replace":
            self.clear_traces()
            self.view.clear_items()
            plot_mode = "overlay"
        elif mode == "overlay":
            plot_mode = "overlay"
        else:
            raise ValueError("Mode must be 'replace' or 'overlay'")

        colour = kwargs.get("colour")
        if callable(colour):
            kwargs = kwargs.copy()
            kwargs["colour"] = colour()

        x_data = x() if callable(x) else x

        if y is None and z is None:
            item = plotter(x_data, mode=plot_mode, **kwargs)
        else:
            y_data = y() if callable(y) else y
            z_data = z() if callable(z) else z
            item = plotter(x_data, y_data, z_data, mode=plot_mode, **kwargs)

        trace = ConsoleSurfaceTrace3D(
            key, x, y, z, item, self, kind=kind, colour=colour, wireframe=wireframe
        )
        self._traces[key] = trace
        self.changed.emit()

        return trace

    def line3d(self, name, x, y=None, z=None, *, mode="replace", **kwargs):
        return self._add_trace3d(
            name, x, y, z, mode=mode, plotter=self.view.line3d, kind="line3d", **kwargs
        )

    def scatter3d(self, name, x, y=None, z=None, *, mode="replace", **kwargs):
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

    def surface3d(self, name, x, y=None, z=None, *, mode="replace", **kwargs):
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

    def wireframe3d(self, name, x, y=None, z=None, *, mode="replace", **kwargs):
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
        changed = False

        for trace in list(self._traces.values()):
            try:
                trace.update()
                changed = True
            except (TypeError, ValueError, FloatingPointError) as exc:
                self._set_status(f"{trace.name}: {exc}")

        if changed:
            self.view.auto_adjust_grid()

    def clear(self):
        self.clear_animations()
        self.clear_sliders()
        self.clear_traces()

    def clear_traces(self):
        for trace in list(self._traces.values()):
            trace.remove()

        self._traces.clear()
        self.changed.emit()

    def clear_sliders(self):
        for param in self._params.values():
            self.param_layout.removeWidget(param.widget)
            param.widget.deleteLater()

        self._params.clear()
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

    def clear_animations(self):
        for animation in self._animations.values():
            animation.pause()
            self.param_layout.removeWidget(animation.widget)
            animation.widget.deleteLater()

        self._animations.clear()
        self.changed.emit()
        self.param_widget.setVisible(self.has_controls())

    def remove_trace(self, name):
        key = str(name).strip()
        trace = self._traces.pop(key, None)
        if trace is None:
            raise KeyError(f"No trace named {key!r}")

        trace.remove()
        self.changed.emit()

        return self.traces()

    def remove_animation(self, name):
        key = str(name).strip()
        animation = self._animations.pop(key, None)
        if animation is None:
            raise KeyError(f"No animation named {key!r}")

        animation.pause()
        self.param_layout.removeWidget(animation.widget)
        animation.widget.deleteLater()
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

        return self.animations()

    def params(self):
        return {name: param.value for name, param in self._params.items()}

    def traces(self):
        return {
            name: {
                "name": trace.name,
                "kind": trace.kind,
            }
            for name, trace in self._traces.items()
        }

    def slider_names(self):
        return list(self._params)

    def trace_names(self):
        return list(self._traces)

    def animation_names(self):
        return list(self._animations)

    def has_controls(self):
        return bool(self._params or self._animations)

    def _set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
