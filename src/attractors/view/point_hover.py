import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtWidgets


class PointHover(QtCore.QObject):
    def __init__(self, view, points, parent=None):
        super().__init__(parent)
        self.view = view
        self.points = points
        self.enabled = False
        self.position = None

        self.marker = gl.GLScatterPlotItem(
            pos=np.empty((0, 3)), color=(1.0, 0.2, 0.1, 1.0), size=12
        )
        self.marker.hide()
        view.addItem(self.marker)
        view.installEventFilter(self)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.view.setMouseTracking(self.enabled)
        if not self.enabled:
            self.clear()

    def clear(self):
        self.timer.stop()
        self.position = None
        self.marker.hide()
        QtWidgets.QToolTip.hideText()
