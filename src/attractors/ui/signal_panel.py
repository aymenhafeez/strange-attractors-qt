import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import prepare_signal, select_interval
from ..workers.spectrum_worker import SpectrumWorker
from .style import PANEL_SURFACE, plot_colours


class SignalPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = None
        self.signal = None
        self.selected_signal = None
        self._interval = None
        self._spectrum = None
        self._spectrum_worker = None
        # track current analysis inputs
        self._spectrum_revision = 0

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

        self.mean_check = QtWidgets.QCheckBox("Remove mean")
        self.mean_check.setChecked(True)
        self.mean_check.setToolTip("Remove mean for PSD calculation")

        self.window_combo = QtWidgets.QComboBox()
        self.window_combo.addItem("Hann", "hann")
        self.window_combo.addItem("Rectangular", "boxcar")

        self.log_check = QtWidgets.QCheckBox("Log power")
        self.log_check.setToolTip("Logarithmic power axis")

        spectrum_row = QtWidgets.QHBoxLayout()
        spectrum_row.addWidget(self.mean_check)
        spectrum_row.addWidget(QtWidgets.QLabel("Window"))
        spectrum_row.addWidget(self.window_combo)
        spectrum_row.addStretch(1)
        spectrum_row.addWidget(self.log_check)

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setLabel("bottom", "Frequency (cycles per unit time)")
        self.spectrum_plot.setLabel("left", "Power spectral density")
        self.spectrum_curve = self.spectrum_plot.plot()
        self.spectrum_curve.setDownsampling(auto=True, method="peak")
        self.spectrum_curve.setClipToView(True)

        self.spectrum_info = QtWidgets.QLabel()
        self.spectrum_info.setWordWrap(True)
        self.spectrum_info.setToolTip(
            "Bin spacing is the distance between FFT frequencies\n"
            "Noise bandwidth describes the analysis window"
        )

        self._spectrum_timer = QtCore.QTimer(self)
        self._spectrum_timer.setSingleShot(True)
        self._spectrum_timer.timeout.connect(self._start_spectrum)

        self.mean_check.toggled.connect(self._queue_spectrum)
        self.window_combo.currentIndexChanged.connect(self._queue_spectrum)
        self.log_check.toggled.connect(self._draw_spectrum)

        time_area = QtWidgets.QWidget()
        time_layout = QtWidgets.QVBoxLayout(time_area)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(4)
        time_layout.addWidget(self.trace, 1)
        time_layout.addLayout(interval_row)
        time_layout.addWidget(self.selection_label)
        time_layout.addWidget(self.info_label)

        spectrum_area = QtWidgets.QWidget()
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_area)
        spectrum_layout.setContentsMargins(0, 0, 0, 0)
        spectrum_layout.setSpacing(4)
        spectrum_layout.addLayout(spectrum_row)
        spectrum_layout.addWidget(self.spectrum_plot, 1)
        spectrum_layout.addWidget(self.spectrum_info)

        plots = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        plots.setChildrenCollapsible(False)
        plots.addWidget(time_area)
        plots.addWidget(spectrum_area)
        plots.setStretchFactor(0, 1)
        plots.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(source_row)
        layout.addWidget(self.status_label)
        layout.addWidget(plots, 1)

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
        self._queue_spectrum()
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
        except ValueError as error:
            self.selection_label.setText(str(error))
            self._queue_spectrum()
            return

        selected = self.selected_signal
        self.selection_label.setText(
            f"Selected: {selected.values.size:,} samples | "
            f"Time: {selected.times[0]:.9g} to {selected.times[-1]:.9g} | "
            f"Span: {selected.times[-1] - selected.times[0]:.9g}"
        )
        self._queue_spectrum()

    def _region_changed(self):
        self._set_interval(*self.region.getRegion())

    def _bounds_changed(self):
        start = self.start_spin.value()
        end = self.end_spin.value()

        if start >= end:
            self.selected_signal = None
            self.selection_label.setText("Start must be before end")
            self._queue_spectrum()
            return

        self._set_interval(start, end)

    def _reset_interval(self):
        if self.signal is not None:
            self._set_interval(self.signal.times[0], self.signal.times[-1])

    def _queue_spectrum(self):
        self._spectrum_revision += 1
        self._spectrum_timer.stop()
        self._spectrum = None
        self.spectrum_curve.clear()
        self.spectrum_info.clear()

        if self.selected_signal is None:
            return
        if self.selected_signal.values.size < 4:
            self.spectrum_info.setText(
                "Spectrum analysis requires at least four samples"
            )
            return

        self.spectrum_info.setText("Updating spectrum")
        self._spectrum_timer.start(150)

    def _start_spectrum(self):
        if self._spectrum_worker is not None:
            return
        if self.selected_signal is None or self.selected_signal.values.size < 4:
            return

        worker = SpectrumWorker(
            self._spectrum_revision,
            self.selected_signal,
            remove_mean=self.mean_check.isChecked(),
            window=self.window_combo.currentData(),
        )
        worker.signals.finished.connect(
            self._on_spectrum_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._spectrum_worker = worker
        QtCore.QThreadPool.globalInstance().start(worker)

    @QtCore.pyqtSlot(int, object, str)
    def _on_spectrum_finished(self, revision, spectrum, error):
        self._spectrum_worker = None

        if revision != self._spectrum_revision:
            if not self._spectrum_timer.isActive():
                self._start_spectrum()
            return

        if spectrum is None:
            self.spectrum_info.setText(error or "Spectrum calculation failed")
            return

        self._spectrum = spectrum
        self._draw_spectrum()

    def _draw_spectrum(self):
        logarithmic = self.log_check.isChecked()
        self.spectrum_plot.setLogMode(x=False, y=logarithmic)

        if self._spectrum is None:
            return

        spectrum = self._spectrum
        coordinate = self.coordinate_combo.currentText()
        self.spectrum_plot.setLabel(
            "left", f"PSD ({coordinate}^2) / (cycles/unit time)"
        )

        self.spectrum_curve.setData(spectrum.frequencies, spectrum.density)
        self.spectrum_plot.enableAutoRange()

        text = (
            f"Bin spacing: {spectrum.bin_spacing:.6g} | "
            f"Noise bandwidth: {spectrum.noise_bandwidth:.6g} | "
            f"Nyquist: {0.5 / self.selected_signal.dt:.6g} cycles/unit time"
        )
        if logarithmic and not (spectrum.density > 0).any():
            text += "\nAll power is zero. Switch off Log power to view it"

        self.spectrum_info.setText(text)

    def apply_theme(self):
        colours = plot_colours()
        for plot in (self.trace, self.spectrum_plot):
            plot.setBackground(colours["plot_background"])
            plot.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        pen = colours["plot_pen"]
        if self._run is not None:
            index = self.trajectory_combo.currentIndex()
            pen = self._run["colours"][index] or pen

        self.curve.setPen(pg.mkPen(pen))
        self.spectrum_curve.setPen(pg.mkPen(colours["alternate_pen"]))
