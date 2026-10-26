# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..core.solution_validation import validate_solutions
from .style import PANEL_SURFACE, plot_colours


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
    field_update_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves = []
        self._markers = []
        self._trajectories = []
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

        self.field_check = QtWidgets.QCheckBox("Vector field")
        self.field_check.setToolTip("Show vector field at system's start time")
        controls.addWidget(self.field_check)

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

        self.field_item = pg.PlotDataItem(connect="finite")
        self.field_item.setZValue(-10)
        self.plot_widget.addItem(self.field_item, ignoreBounds=True)
        self.field_item.hide()

        self._field_timer = QtCore.QTimer(self)
        self._field_timer.setSingleShot(True)
        self._field_timer.setInterval(100)
        self._field_timer.timeout.connect(self.field_update_requested.emit)

        self.field_check.toggled.connect(self._on_field_toggled)
        self.view_box.sigRangeChanged.connect(lambda *_: self.request_field_update())

        self.apply_theme()

    def _set_seeding_enabled(self, enabled):
        self.view_box.seeding_enabled = enabled

    def set_trajectories(self, trajectories):
        self._trajectories = [dict(entry) for entry in trajectories]
        self._apply_trajectory_styles()

    def _apply_trajectory_styles(self):
        colours = plot_colours()
        palette = colours["trajectory_palette"]

        for i, curve in enumerate(self._curves):
            trajectory = self._trajectories[i] if i < len(self._trajectories) else {}

            default_colour = palette[i % len(palette)]
            colour = QtGui.QColor(pg.mkColor(trajectory.get("colour", default_colour)))
            alpha = trajectory.get("alpha", 1.0)
            colour.setAlphaF(colour.alphaF() * np.clip(alpha, 0.0, 1.0))
            self._markers[i].setSymbolBrush(colour)
            size = trajectory.get("size", colours["scatter_size"])
            line_mode = trajectory.get("render_mode", "line") == "line"

            if line_mode:
                curve.setSymbol(None)
                curve.setPen(pg.mkPen(colour, width=size))
            else:
                curve.setPen(None)
                curve.setSymbol("o")
                curve.setSymbolPen(None)
                curve.setSymbolBrush(colour)
                curve.setSymbolSize(size)

    def display_solutions(self, solutions, initial_conditions=None):
        if not solutions:
            self.clear()
            return

        valid, message = validate_solutions(solutions, dimension=2)
        if not valid:
            raise ValueError(message)

        while len(self._curves) > len(solutions):
            self.plot_widget.removeItem(self._curves.pop())
            self.plot_widget.removeItem(self._markers.pop())

        while len(self._curves) < len(solutions):
            self._curves.append(self.plot_widget.plot())
            marker = self.plot_widget.plot(
                pen=None, symbol="o", symbolSize=6, symbolPen=None
            )
            marker.setZValue(10)
            self._markers.append(marker)

        starts = (
            initial_conditions
            if initial_conditions is not None
            else [solution[0] for solution in solutions]
        )

        for curve, marker, solution, start in zip(
            self._curves, self._markers, solutions, starts, strict=True
        ):
            curve.setData(solution[:, 0], solution[:, 1])
            marker.setData([start[0]], [start[1]])

        self._apply_trajectory_styles()

        if not self._has_data:
            self.fit()

        self._has_data = True

    def _on_field_toggled(self, checked):
        if checked:
            self.request_field_update()
        else:
            self._field_timer.stop()
            self.field_item.hide()

    def request_field_update(self):
        if self.field_check.isChecked():
            self._field_timer.start()

    def set_vector_field(self, x, y):
        self.field_item.setData(x, y)
        self.field_item.setVisible(self.field_check.isChecked())

    def clear(self):
        for curve in self._curves:
            self.plot_widget.removeItem(curve)

        for marker in self._markers:
            self.plot_widget.removeItem(marker)

        self._curves.clear()
        self._markers.clear()
        self._has_data = False
        self._field_timer.stop()
        self.field_item.clear()
        self.field_item.hide()

    def fit(self):
        self.view_box.autoRange(padding=0.08)

    def apply_theme(self):
        colours = plot_colours()
        self.plot_widget.setBackground(colours["plot_background"])
        self.plot_widget.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        for position in ("bottom", "left"):
            axis = self.plot_widget.getAxis(position)
            axis.setPen(pg.mkPen(colours["colourbar_text"]))
            axis.setTextPen(pg.mkPen(colours["colourbar_text"]))

        self._apply_trajectory_styles()

        self.field_item.setPen(pg.mkPen("#555555" if colours["is_dark"] else "#aaaaaa"))
