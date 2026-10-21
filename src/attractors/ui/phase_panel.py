import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore


class _PhaseViewBox(pg.ViewBox):
    seed_requested = QtCore.pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.seeding_enabled = False

    def mouseClickEvent(self, ev):
        if (
            self.seeding_enabled
            and ev.button() == QtCore.Qt.MouseButton.LeftButton
            and not ev.double()
        ):
            point = self.mapSceneToView(ev.scenePos())
            x, y = float(point.x()), float(point.y())
            if np.isfinite(x) and np.isfinite(y):
                self.seed_requested.emit(x, y)

            ev.accept()

            return

        super().mouseClickEvent(ev)
