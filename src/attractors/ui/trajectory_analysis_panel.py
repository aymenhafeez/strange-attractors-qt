# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import sample_times, trajectory_signal
from .style import PANEL_SURFACE, plot_colours


class TrajectoryAnalysisPanel(QtWidgets.QWidget):
    play_requested = QtCore.pyqtSignal()
    seek_requested = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = None
        self._play_bounds = None

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_SURFACE)

        self.trajectory_combo = QtWidgets.QComboBox()
        self.coordinate_combo = QtWidgets.QComboBox()
        self.comparison_combo = QtWidgets.QComboBox()

        source_row = QtWidgets.QHBoxLayout()
        for label, combo in (
            ("Trajectory:", self.trajectory_combo),
            ("Coordinate:", self.coordinate_combo),
            ("Compare:", self.comparison_combo),
        ):
            source_row.addWidget(QtWidgets.QLabel(label))
            source_row.addWidget(combo)

        source_row.addStretch()

        self.trace = pg.PlotWidget()
        self.trace.setLabel("bottom", "Time")
        self.curve = self.trace.plot()

        self.separation_plot = pg.PlotWidget()
        self.separation_plot.setLabel("bottom", "Time")
        self.separation_plot.setLabel("left", "Log separation")
        self.separation_plot.setLogMode(y=True)
        self.separation_plot.setXLink(self.trace)
        self.separation_curve = self.separation_plot.plot()

        self.cursors = []
        for plot, curve in (
            (self.trace, self.curve),
            (self.separation_plot, self.separation_curve),
        ):
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)
            cursor = pg.InfiniteLine(angle=90, movable=False)
            plot.addItem(cursor, ignoreBounds=True)
            cursor.hide()
            self.cursors.append(cursor)

        plots = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        plots.addWidget(self.trace)
        plots.addWidget(self.separation_plot)
        plots.setStretchFactor(0, 1)
        plots.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(source_row)
        layout.addWidget(plots, 1)

        self.curve.setPen(pg.mkPen(pen))
        self.separation_curve.setPen(pg.mkPen(colours["alternate_pen"]))
        for cursor in self.cursors:
            cursor.setPen(
                pg.mkPen(
                    colours["crosshair"],
                    width=colours["scatter_size"],
                    style=QtCore.Qt.PenStyle.DashLine,
                )
            )
