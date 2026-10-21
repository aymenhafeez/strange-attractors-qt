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


class PhasePortraitPanel(QtWidgets.QWidget):
    seed_requested = QtCore.pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves = []
        self._has_data = None

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_SURFACE)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        controls = QtWidgets.QHBoxLayout()

        self.seed_check = QtWidgets.QCheckBox("Click to add trajectory")
        self.seed_check.setToolTip(
            "Click insider the plot to choose an initial conditions"
        )
        controls.addWidget(self.seed_check)
        controls.addStretch()

        self.fit_button = QtWidgets.QPushButton("Fit")
        self.fit_button.clicked.connect(self.fit)
        controls.addWidget(self.fit_button)

        layout.addLayout(controls)

        self.view_box = _PhaseViewBox()
        self.plot_widget = pg.PlotWidget(viewBox=self.view_box)
        self.plot_widget.setLabel("bottom", "x")
        self.plot_widget.setLabel("left", "y")

        self.view_box.setAspectLocked(True)
        self.view_box.disableAutoRange()
        self.view_box.setRange(xRange=(-2, 2), yRange=(-2, 2), padding=0)

        layout.addWidget(self.plot_widget, 1)

        self.seed_check.toggled.connect(self._set_seeding_enabled)
        self.view_box.seed_requested.connect(self.seed_requested.emit)
