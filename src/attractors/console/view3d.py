import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets

from ..view.camera_controller import CameraController
from ..view.grid_overlay import GridOverlay


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

