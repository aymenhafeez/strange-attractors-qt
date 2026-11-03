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

        self.play_button = QtWidgets.QPushButton("Play")
        self.play_button.clicked.connect(self.play_requested.emit)
        self.scrubber = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 10000)
        self.scrubber.valueChanged.connect(self._seek)
        self.time_label = QtWidgets.QLabel()
        self.source_label = QtWidgets.QLabel("No completed run")

        transport = QtWidgets.QHBoxLayout()
        transport.addWidget(self.play_button)
        transport.addWidget(self.scrubber, 1)
        transport.addWidget(self.time_label)
        transport.addWidget(self.source_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(source_row)
        layout.addWidget(plots, 1)
        layout.addLayout(transport)

        self.trajectory_combo.currentIndexChanged.connect(self._show_trace)
        self.trajectory_combo.currentIndexChanged.connect(self._show_separation)
        self.coordinate_combo.currentIndexChanged.connect(self._show_trace)
        self.comparison_combo.currentIndexChanged.connect(self._show_separation)

        self.set_source(None, {})
        self.set_playback_range(0.0, 0.0)
        self.apply_theme()

    def set_source(self, run, state):
        fresh = bool(
            run is not None
            and state.get("valid")
            and not state.get("stale")
            and not state.get("solving")
            and state.get("request_id") == run["request_id"]
        )
        if state.get("solving"):
            text = "Solving"
        elif state.get("last_error"):
            text = "Solve failed"
        elif run is None:
            text = "No completed run"
        elif fresh:
            text = "Completed run"
        elif state.get("partial") and state.get("request_id") == run["request_id"]:
            text = "Preview run"
        else:
            text = "Settings changed"

        if run is not None and not fresh:
            text += ", playback unavailable"

        self.source_label.setText(text)
        self.source_label.setToolTip(state.get("last_error") or "")

        if run is self._run:
            return

        trajectory = max(0, self.trajectory_combo.currentIndex())
        coordinate = self.coordinate_combo.currentText()
        comparison = self.comparison_combo.currentData()
        self._run = run

        with (
            QtCore.QSignalBlocker(self.trajectory_combo),
            QtCore.QSignalBlocker(self.coordinate_combo),
            QtCore.QSignalBlocker(self.comparison_combo),
        ):
            self.trajectory_combo.clear()
            self.coordinate_combo.clear()
            self.comparison_combo.clear()
            self.comparison_combo.addItem("None", None)

            if run is not None:
                self.trajectory_combo.addItems(run["labels"])
                self.coordinate_combo.addItems(run["variables"])
                for index, label in enumerate(run["labels"]):
                    self.comparison_combo.addItem(label, index)

                self.trajectory_combo.setCurrentIndex(
                    min(trajectory, len(run["solutions"]) - 1)
                )
                self.coordinate_combo.setCurrentText(
                    coordinate
                    if coordinate in run["variables"]
                    else run["variables"][0]
                )
                self.comparison_combo.setCurrentIndex(
                    max(0, self.comparison_combo.findData(comparison))
                )

        for combo in (
            self.trajectory_combo,
            self.coordinate_combo,
            self.comparison_combo,
        ):
            combo.setEnabled(run is not None)

        self._show_trace()
        self._show_separation()

    def _show_trace(self):
        self.curve.clear()
        if self._run is None:
            return

        index = self.trajectory_combo.currentIndex()
        coordinate = self.coordinate_combo.currentText()
        column = self._run["variables"].index(coordinate)
        signal = trajectory_signal(
            self._run["solutions"][index],
            column,
            t_min=self._run["t_min"],
            t_max=self._run["trajectory_specs"][index]["t_max"],
        )
        self.curve.setData(signal.times, signal.values)
        self.trace.setLabel("left", coordinate)
        self.trace.setTitle(f"{coordinate} vs time")
        self.trace.enableAutoRange()
        self.apply_theme()

    def _show_separation(self):
        self.separation_curve.clear()
        self.separation_plot.setTitle("Select comparison trajectory")
        if self._run is None:
            return

        a = self.trajectory_combo.currentIndex()
        b = self.comparison_combo.currentData()
        if b is None:
            return
        if a == b:
            self.separation_plot.setTitle("Choose two different trajectories")
            return

        solutions = self._run["solutions"]
        specs = self._run["trajectory_specs"]
        t_min = self._run["t_min"]
        times_a = sample_times(t_min, specs[a]["t_max"], len(solutions[a]))
        times_b = sample_times(t_min, specs[b]["t_max"], len(solutions[b]))
        length = min(len(times_a), len(times_b))

        if not np.array_equal(times_a[:length], times_b[:length]):
            self.separation_plot.setTitle("Matching sample times required")
            return

        distance = np.linalg.norm(solutions[a][:length] - solutions[b][:length], axis=1)
        distance[distance == 0] = np.nan
        self.separation_plot.setTitle(
            f"{self._run['labels'][a]} - {self._run['labels'][b]}"
        )
        self.separation_curve.setData(times_a[:length], distance)

    def set_playback_range(self, start, end):
        self._play_bounds = (start, end) if end > start else None
        enabled = self._play_bounds is not None
        self.play_button.setEnabled(enabled)
        self.scrubber.setEnabled(enabled)

        for cursor in self.cursors:
            cursor.setVisible(enabled)

        if not enabled:
            self.time_label.clear()

    def set_playing(self, playing):
        self.play_button.setText("Pause" if playing else "Play")

    def set_playback_time(self, time):
        if self._play_bounds is None:
            return

        start, end = self._play_bounds
        fraction = np.clip((time - start) / (end - start), 0, 1)
        with QtCore.QSignalBlocker(self.scrubber):
            self.scrubber.setValue(round(fraction * 10000))

        for cursor in self.cursors:
            cursor.setValue(time)

        self.time_label.setText(f"t = {time:6.2f}")

    def _seek(self, value):
        if self._play_bounds is not None:
            start, end = self._play_bounds
            self.seek_requested.emit(start + value / 10000 * (end - start))

    def apply_theme(self):
        colours = plot_colours()
        for plot in (self.trace, self.separation_plot):
            plot.setBackground(colours["plot_background"])
            plot.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        pen = colours["plot_pen"]
        if self._run is not None:
            index = self.trajectory_combo.currentIndex()
            pen = self._run["colours"][index] or pen

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
