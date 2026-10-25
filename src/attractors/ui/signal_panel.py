# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import prepare_signal, select_interval
from ..workers.spectrogram_worker import SpectrogramWorker
from ..workers.spectrum_worker import SpectrumWorker
from .style import SIGNAL_PANEL, SIGNAL_PLOTS, plot_colours


class SignalPanel(QtWidgets.QWidget):
    status_changed = QtCore.pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = {"spectrum": ("", False), "spectrogram": ("", False)}
        self._run = None
        self.signal = None
        self.selected_signal = None
        self._interval = None
        self._spectrum = None
        self._spectrum_worker = None
        # track current analysis inputs
        self._spectrum_revision = 0
        self._spectrum_waiting = False
        self._syncing_time_range = False
        self._spectrogram = None
        self._spectrogram_worker = None
        self._spectrogram_revision = 0
        self._spectrogram_waiting = False
        self._setting_spectrogram_frequency = False

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(SIGNAL_PANEL)

        self.trajectory_combo = QtWidgets.QComboBox()
        self.coordinate_combo = QtWidgets.QComboBox()
        self.trajectory_combo.setEnabled(False)
        self.coordinate_combo.setEnabled(False)

        self.status_label = QtWidgets.QLabel("No completed run")
        self.status_label.setWordWrap(True)

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
        self.region.sigRegionChangeFinished.connect(self._refresh_analysis)

        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.start_spin, self.end_spin):
            spin.setDecimals(5)
            spin.setKeyboardTracking(False)
            spin.setEnabled(False)
            spin.valueChanged.connect(self._bounds_changed)

        self.full_button = QtWidgets.QPushButton("Full record")
        self.full_button.setEnabled(False)
        self.full_button.clicked.connect(self._reset_interval)

        self.selection_label = QtWidgets.QLabel()
        self.selection_label.setWordWrap(True)

        self.mean_check = QtWidgets.QCheckBox("Remove mean")
        self.mean_check.setChecked(True)

        self.window_combo = QtWidgets.QComboBox()
        self.window_combo.addItem("Hann", "hann")
        self.window_combo.addItem("Rectangular", "boxcar")

        self.log_check = QtWidgets.QCheckBox("Log power")
        self.log_check.setChecked(True)

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setLabel("bottom", "Frequency (cycles per unit time)")
        self.spectrum_plot.setLabel("left", "Power spectral density")
        self.spectrum_curve = self.spectrum_plot.plot()
        self.spectrum_curve.setDownsampling(auto=True, method="peak")
        self.spectrum_curve.setClipToView(True)

        self.duration_spin = QtWidgets.QDoubleSpinBox()
        self.duration_spin.setDecimals(5)
        self.duration_spin.setRange(1e-12, 1e12)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setKeyboardTracking(False)

        self.overlap_spin = QtWidgets.QDoubleSpinBox()
        self.overlap_spin.setRange(0.0, 95.0)
        self.overlap_spin.setDecimals(1)
        self.overlap_spin.setValue(50.0)
        self.overlap_spin.setSingleStep(5.0)
        self.overlap_spin.setSuffix(" %")
        self.overlap_spin.setKeyboardTracking(False)

        self.colour_scale_combo = QtWidgets.QComboBox()
        self.colour_scale_combo.addItem("Linear PSD", "linear")
        self.colour_scale_combo.addItem("dB re 1", "db")

        self.frequency_view_combo = QtWidgets.QComboBox()
        self.frequency_view_combo.addItem("Auto band", "auto")
        self.frequency_view_combo.addItem("Full band", "full")
        self.frequency_view_combo.addItem("Manual", "manual")
        self.frequency_view_combo.currentIndexChanged.connect(
            self._apply_spectrogram_frequency
        )

        for control, minimum_width in (
            (self.duration_spin, 70),
            (self.overlap_spin, 60),
            (self.frequency_view_combo, 70),
            (self.colour_scale_combo, 70),
        ):
            policy = control.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Ignored)
            control.setSizePolicy(policy)
            control.setMinimumWidth(minimum_width)

        self.spectrogram_plot = pg.PlotWidget()
        self.spectrogram_plot.setLabel("bottom", "Time")
        self.spectrogram_plot.setLabel("left", "Frequency (cycles per unit time)")

        trace_view = self.trace.getViewBox()
        spectrogram_view = self.spectrogram_plot.getViewBox()
        spectrogram_view.disableAutoRange()
        trace_view.sigXRangeChanged.connect(self._sync_time_range)
        spectrogram_view.sigXRangeChanged.connect(self._sync_time_range)
        spectrogram_view.sigYRangeChanged.connect(self._spectrogram_frequency_changed)

        self.spectrogram_image = pg.ImageItem(axisOrder="row-major")
        self.spectrogram_plot.addItem(self.spectrogram_image)

        self.spectrogram_colour_bar = pg.ColorBarItem(
            values=(0.0, 1.0),
            colorMap=pg.colormap.get("viridis"),
            label="Power spectral density",
            interactive=False,
            colorMapMenu=False,
        )
        self.spectrogram_colour_bar.setImageItem(
            self.spectrogram_image,
            insert_in=self.spectrogram_plot.getPlotItem(),
        )

        self._spectrum_timer = QtCore.QTimer(self)
        self._spectrum_timer.setSingleShot(True)
        self._spectrum_timer.timeout.connect(self._start_spectrum)
        self._spectrogram_timer = QtCore.QTimer(self)
        self._spectrogram_timer.setSingleShot(True)
        self._spectrogram_timer.timeout.connect(self._start_spectrogram)

        self.duration_spin.valueChanged.connect(self._queue_spectrogram)
        self.overlap_spin.valueChanged.connect(self._queue_spectrogram)
        self.colour_scale_combo.currentIndexChanged.connect(self._draw_spectrogram)
        self.colour_scale_combo.setCurrentIndex(1)

        self.mean_check.toggled.connect(self._queue_analysis)
        self.window_combo.currentIndexChanged.connect(self._queue_analysis)
        self.log_check.toggled.connect(self._draw_spectrum)

        self.trajectory_combo.setMinimumContentsLength(18)
        self.trajectory_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.log_check.setText("Log power")

        self.colour_scale_combo.setAccessibleName("Spectrogram colour scale")

        source_row = QtWidgets.QHBoxLayout()
        source_row.setContentsMargins(0, 5, 0, 0)
        source_row.setSpacing(8)
        source_row.addWidget(QtWidgets.QLabel("Trajectory"))
        source_row.addWidget(self.trajectory_combo)
        source_row.addWidget(QtWidgets.QLabel("Coordinate"))
        source_row.addWidget(self.coordinate_combo)
        source_row.addSpacing(8)
        source_row.addWidget(QtWidgets.QLabel("Window"))
        source_row.addWidget(self.window_combo)
        source_row.addWidget(self.mean_check)
        self.status_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.status_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        source_row.addStretch(1)

        interval_row = QtWidgets.QHBoxLayout()
        interval_row.setSpacing(8)
        interval_row.addSpacing(8)
        interval_row.addWidget(QtWidgets.QLabel("Start"))
        interval_row.addWidget(self.start_spin)
        interval_row.addWidget(QtWidgets.QLabel("End"))
        interval_row.addWidget(self.end_spin)
        interval_row.addWidget(self.full_button)
        interval_row.addStretch(1)

        time_area = QtWidgets.QFrame()
        time_area.setObjectName("panelSurface")
        time_area.setStyleSheet(SIGNAL_PLOTS)
        time_area.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        time_layout = QtWidgets.QVBoxLayout(time_area)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(4)
        time_layout.addLayout(interval_row)
        time_layout.addWidget(self.trace, 1)
        # time_layout.addWidget(self.selection_label)

        spectrum_header = QtWidgets.QWidget()
        spectrum_row = QtWidgets.QHBoxLayout(spectrum_header)
        spectrum_row.setContentsMargins(3, 0, 0, 0)
        spectrum_row.addWidget(self.log_check)

        spectrogram_header = QtWidgets.QWidget()
        spectrogram_row = QtWidgets.QHBoxLayout(spectrogram_header)
        spectrogram_row.setContentsMargins(3, 0, 3, 0)
        spectrogram_row.setSpacing(1)
        spectrogram_row.addWidget(QtWidgets.QLabel("Duration"))
        spectrogram_row.addWidget(self.duration_spin)
        spectrogram_row.addWidget(QtWidgets.QLabel("Overlap"))
        spectrogram_row.addWidget(self.overlap_spin)
        spectrogram_row.addWidget(self.frequency_view_combo)
        spectrogram_row.addWidget(self.colour_scale_combo)

        self.spectrum_plot.setTitle(None)
        self.spectrogram_plot.setTitle(None)

        spectrum_area = QtWidgets.QFrame()
        spectrum_area.setObjectName("panelSurface")
        spectrum_area.setStyleSheet(SIGNAL_PLOTS)
        spectrum_area.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_area)
        spectrum_layout.setContentsMargins(0, 0, 0, 0)
        spectrum_layout.setSpacing(4)
        spectrum_layout.addWidget(spectrum_header)
        spectrum_layout.addWidget(self.spectrum_plot, 1)

        spectrogram_area = QtWidgets.QFrame()
        spectrogram_area.setObjectName("panelSurface")
        spectrogram_area.setStyleSheet(SIGNAL_PLOTS)
        spectrogram_area.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        spectrogram_layout = QtWidgets.QVBoxLayout(spectrogram_area)
        spectrogram_layout.setContentsMargins(0, 0, 0, 0)
        spectrogram_layout.setSpacing(4)
        spectrogram_layout.addWidget(spectrogram_header)
        spectrogram_layout.addWidget(self.spectrogram_plot, 1)

        spectral_plots = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        spectral_plots.setChildrenCollapsible(False)
        spectral_plots.addWidget(spectrum_area)
        spectral_plots.addWidget(spectrogram_area)
        spectral_plots.setStretchFactor(0, 1)
        spectral_plots.setStretchFactor(1, 1)

        plots = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        plots.setChildrenCollapsible(False)
        plots.addWidget(time_area)
        plots.addWidget(spectral_plots)
        plots.setStretchFactor(0, 1)
        plots.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(source_row)
        layout.addWidget(plots, 1)
        # layout.addWidget(self.status_label)

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
