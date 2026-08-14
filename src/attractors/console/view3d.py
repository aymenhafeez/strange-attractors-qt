import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.docking import AreaBoundDock as Dock
from ..view.camera_controller import CameraController
from ..view.grid_overlay import GridOverlay


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

    if len(points) == 0:
        raise ValueError(f"{name} cannot be empty")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} can't contain non finite values")

    return points


class ConsoleView3D:
    def __init__(self, status_callback=None):
        self._manager = None
        self._items = []
        self._status_callback = status_callback

        self.host = QtWidgets.QWidget()
        # layout reserved name in Qt so using v_layout instead
        self.v_layout = QtWidgets.QVBoxLayout(self.host)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)

        self.view = gl.GLViewWidget()
        self.camera_controller = CameraController(self.view)
        self.grid_overlay = GridOverlay(self.view)
        self.grid_overlay.build_grid(50.0)

        self.v_layout.addWidget(self.view, 1)

        self.param_widget = QtWidgets.QFrame()
        self.param_layout = QtWidgets.QVBoxLayout(self.param_widget)
        self.param_layout.setContentsMargins(0, 0, 0, 0)
        self.param_layout.setSpacing(4)

        self.v_layout.addWidget(self.param_widget)

    def __repr__(self):
        return "ConsoleView3D()"

    def clear(self):
        for item in self._items:
            self.view.removeItem(item)
        self._items.clear()

    def auto_range(self):
        # TODO: fill this in once items are exposing their data
        pass

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

        item = gl.GLLinePlotItem(
            pos=points,
            color=colour,
            width=width,
            antialias=antialias,
            mode="line_strip",
        )

        self.view.addItem(item)
        self._items.append(item)
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

        item = gl.GLScatterPlotItem(
            pos=points,
            color=colour,
            size=size,
            pxMode=px_mode,
        )

        item.setGLOptions("additive")
        self.view.addItem(item)
        self._items.append(item)
        self.camera_controller.fit_camera_to_solutions([points])

        return item


# adapting this from ConsolePlotManager, will need to generalise to 3D
class ConsoleView3DManager(QtCore.QObject):
    views_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    view_removed = QtCore.pyqtSignal(str, object)
    view_cleared = QtCore.pyqtSignal(str, object)

    def __init__(
        self, dock_area, default_name, default_view, default_dock, status_callback=None
    ):
        super().__init__(dock_area)
        self._dock_area = dock_area
        self._views = {default_name: default_view}
        self._docks = {default_name: default_dock}
        self._default_name = default_name
        self._current_name = default_name
        self._status_callback = status_callback
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
        dock.sigClosed.connect(lambda _dock, view_name=key: self._forget(view_name))
        self._dock_area.addDock(
            dock,
            position="above",
            relativeTo=self._docks[self._default_name],
        )
        self._views[key] = view
        self._docks[key] = dock
        if activate:
            self._set_current_name(key)
            dock.raiseDock()
        self.views_changed.emit()

        return view

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

    def auto_range(self):
        self.current.auto_range()

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
