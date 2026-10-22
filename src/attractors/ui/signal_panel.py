import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import prepare_signal, select_interval
from .style import PANEL_SURFACE, plot_colours


class SignalPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = None
        self.signal = None
        self.selected_signal = None
        self._interval = None

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_SURFACE)

        self.trajectory_combo = QtWidgets.QComboBox()
        self.coordinate_combo = QtWidgets.QComboBox()
        self.trajectory_combo.setEnabled(False)
        self.coordinate_combo.setEnabled(False)

        source_row = QtWidgets.QHBoxLayout()
        source_row.addWidget(QtWidgets.QLabel("Trajectory"))
        source_row.addWidget(self.trajectory_combo, 1)
        source_row.addWidget(QtWidgets.QLabel("Coordonate"))
        source_row.addWidget(self.coordinate_combo)

        self.status_label = QtWidgets.QLabel("No completed run")
        self.status_label.setWordWrap(True)
        self.info_label = QtWidgets.QLabel("No completed run")
        self.info_label.setWordWrap(True)

        self.trace = pg.PlotWidget()
        self.trace.setLabel("bottom", "Time")
        self.curve = self.trace.plot()
        self.curve.setDownsampling(auto=True, method="peak")
        self.curve.setClipToView(True)

        self.region = pg.LinearRegionItem(swapMode="block")
        self.region.setZValue(10)
        self.trace.addItem(self.region, ignoreBounds=True)
        self.region.hide()
        self.region.sigRegionChanged.connect(self._region_changed)

        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.start_spin, self.end_spin):
            spin.setDecimals(12)
            spin.setKeyboardTracking(False)
            spin.setEnabled(False)
            spin.valueChanged.connect(self._bounds_changed)

        self.full_button = QtWidgets.QPushButton("Full record")
        self.full_button.setEnabled(False)
        self.full_button.clicked.connect(self._reset_interval)

        interval_row = QtWidgets.QHBoxLayout()
        interval_row.addWidget(QtWidgets.QLabel("Start"))
        interval_row.addWidget(self.start_spin, 1)
        interval_row.addWidget(QtWidgets.QLabel("End"))
        interval_row.addWidget(self.end_spin, 1)
        interval_row.addWidget(self.full_button)

        self.selection_label = QtWidgets.QLabel()
        self.selection_label.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        layout.addLayout(source_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.trace, 1)
        layout.addLayout(interval_row)
        layout.addWidget(self.selection_label)
        layout.addWidget(self.info_label)

        self.trajectory_combo.currentIndexChanged.connect(self._show_trace)
        self.coordinate_combo.currentIndexChanged.connect(self._show_trace)
        self.apply_theme()

    def set_source(self, run, state):
        fresh = (
            run is not None
            and state.get("valid")
            and not state.get("stale")
            and not state.get("solving")
            and state.get("request_id") == run["request_id"]
        )

        if state.get("last_error"):
            text = f"Solve failed: {state['last_error']}"
        elif state.get("solving"):
            text = "Solving"
        elif run is None:
            text = "No completed run"
        elif fresh:
            text = "Completed run"
        else:
            text = "Settings changed"

        if run is not None and not fresh:
            text += " - showing previous completed run"
        self.status_label.setText(text)

        if run is self._run:
            return

        trajectory = max(self.trajectory_combo.currentIndex(), 0)
        coordinate = self.coordinate_combo.currentText()
        self._run = run

        with (
            QtCore.QSignalBlocker(self.trajectory_combo),
            QtCore.QSignalBlocker(self.coordinate_combo),
        ):
            self.trajectory_combo.clear()
            self.coordinate_combo.clear()

            if run is not None:
                for label, spec in zip(run["labels"], run["trajectory_specs"]):
                    initial = ", ".join(f"{v:g}" for v in spec["ic"])
                    self.trajectory_combo.addItem(f"{label}: ({initial})")

                self.trajectory_combo.setCurrentIndex(
                    min(trajectory, self.trajectory_combo.count() - 1)
                )
                self.coordinate_combo.addItems(run["variables"])
                self.coordinate_combo.setCurrentText(
                    coordinate
                    if coordinate in run["variables"]
                    else run["variables"][0]
                )
                parameters = ", ".join(
                    f"{name}={value:g}" for name, value in run["parameters"].items()
                )
                self.trajectory_combo.setToolTip(f"{run['attractor']}\n{parameters}")
            else:
                self.trajectory_combo.setToolTip("")

        self.trajectory_combo.setEnabled(run is not None)
        self.coordinate_combo.setEnabled(run is not None)
        self._show_trace()

    def _show_trace(self):
        self.signal = None
        self.selected_signal = None
        self.selection_label.clear()
        self.region.hide()
        for widget in (self.start_spin, self.end_spin, self.full_button):
            widget.setEnabled(False)

        if self._run is None:
            self._interval = None
            self.curve.clear()
            self.trace.setLabel("left", "Value")
            self.info_label.clear()
            return

        index = self.trajectory_combo.currentIndex()
        coordinate = self.coordinate_combo.currentText()
        column = self._run["variables"].index(coordinate)
        solution = self._run["solutions"][index]
        spec = self._run["trajectory_specs"][index]
        dt = (spec["t_max"] - self._run["t_min"]) / spec["n"]

        try:
            self.signal = prepare_signal(
                solution[:, column],
                dt=dt,
                t0=self._run["t_min"] + dt,
            )
        except ValueError as error:
            self.curve.clear()
            self.info_label.setText(str(error))
            return

        self.curve.setData(self.signal.times, self.signal.values)
        self.trace.setLabel("left", coordinate)
        self.trace.enableAutoRange()
        self.info_label.setText(
            f"Record: {self.signal.values.size:,} samples | dt = {dt:.6g} | "
            f"Rate = {1.0 / dt:.6g} samples/time unit"
        )

        first = float(self.signal.times[0])
        last = float(self.signal.times[-1])
        start, end = self._interval or (first, last)
        start = min(max(start, first), last)
        end = min(max(end, first), last)

        if start >= end:
            start, end = first, last

        with (
            QtCore.QSignalBlocker(self.region),
            QtCore.QSignalBlocker(self.start_spin),
            QtCore.QSignalBlocker(self.end_spin),
        ):
            self.region.setBounds((first, last))
            for spin in (self.start_spin, self.end_spin):
                spin.setRange(first, last)
                spin.setSingleStep(self.signal.dt)

        for widget in (self.start_spin, self.end_spin, self.full_button):
            widget.setEnabled(True)

        self.region.show()
        self._set_interval(start, end)
        self.apply_theme()

    def _set_interval(self, start, end):
        if self.signal is None:
            return

        with (
            QtCore.QSignalBlocker(self.region),
            QtCore.QSignalBlocker(self.start_spin),
            QtCore.QSignalBlocker(self.end_spin),
        ):
            self.region.setRegion((start, end))
            start, end = self.region.getRegion()
            self.start_spin.setValue(start)
            self.end_spin.setValue(end)

        self._interval = (start, end)
        self.selected_signal = None

        try:
            self.selected_signal = select_interval(self.signal, start, end)
        except ValueError as e:
            self.selection_label.setText(str(e))
            return

        selected = self.selected_signal
        self.selection_label.setText(
            f"Selected: {selected.values.size:,} samples | "
            f"Time: {selected.times[0]:.9g} to {selected.times[0]:.9g} "
            f"Span: {selected.times[-1] - selected.times[0]:.9g}"
        )

    def _region_changed(self):
        self._set_interval(*self.region.getRegion())

    def _bounds_changed(self):
        start = self.start_spin.value()
        end = self.end_spin.value()

        if start >= end:
            self.selected_signal = None
            self.selection_label.setText("Start must be before end")
            return

        self._set_interval(start, end)

    def _reset_interval(self):
        if self.signal is not None:
            self._set_interval(self.signal.times[0], self.signal.times[-1])

    def apply_theme(self):
        colours = plot_colours()
        self.trace.setBackground(colours["plot_background"])
        self.trace.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        pen = colours["plot_pen"]
        if self._run is not None:
            index = self.trajectory_combo.currentIndex()
            pen = self._run["colours"][index] or pen

        self.curve.setPen(pg.mkPen(pen))
