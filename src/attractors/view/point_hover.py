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

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.update_hover)

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

    def update_hover(self):
        if self.position is None:
            return

        sets = [
            points for points in self.points() if points is not None and len(points)
        ]
        width, height = self.view.width(), self.view.height()
        if not sets or width == 0 or height == 0:
            self.clear()
            return

        points = np.concatenate(sets)
        transform = (
            self.view.projectionMatrix((0, 0, width, height), self.view.getViewport())
            * self.view.viewMatrix()
        )
        matrix = np.array(
            [
                [row.x(), row.y(), row.z(), row.w()]
                for row in (transform.row(i) for i in range(4))
            ]
        )

        coordinates = np.column_stack((points, np.ones(len(points))))
        clip = coordinates @ matrix.T
        valid = clip[:, 3] > 0
        ndc = np.zeros((len(points), 3))
        ndc[valid] = clip[valid, :3,] / clip[valid, 3, None]
        valid &= np.all(np.abs(ndc) <= 1, axis=1)

        x = (ndc[:, 0] + 1) * width / 2
        y = (1 - ndc[:, 1]) * height / 2
        distance = (x - self.position.x()) ** 2 + (y - self.position.y()) ** 2
        distance[~valid] = np.inf
        index = int(np.argmin(distance))

        if distance[index] > 12**2:
            self.marker.hide()
            QtWidgets.QToolTip.hideText()
            return

        point = points[index]
        self.marker.setData(pos=point[None, :])
        self.marker.show()
        QtWidgets.QToolTip.showText(
            self.view.mapToGlobal(self.position.toPoint() + QtCore.QPoint(12, 12)),
            f"x={point[0]:.3f}, y={point[1]:.3f}, z={point[2]:.3f}"
        )
