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
        self._analysis_source = None
        self._spectrum_dt = None
        self._spectrogram_dt = None
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

        self.fft_check = QtWidgets.QCheckBox("FFT")
        self.fft_check.setChecked(False)

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
        # plot options -> Transforms -> FFT
        fft_control = self.spectrum_plot.getPlotItem().ctrl.fftCheck
        self.fft_check.toggled.connect(fft_control.setChecked)
        fft_control.toggled.connect(self.fft_check.setChecked)
        self.fft_check.toggled.connect(self._draw_spectrum)

        self.trajectory_combo.setMinimumContentsLength(18)
        self.trajectory_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )

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
        spectrum_row.addWidget(self.fft_check)
        spectrum_row.addStretch(1)

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

    def _set_status(self, kind, message="", *, error=False):
        self._status[kind] = (message, error)

        messages = []
        has_error = False

        for name, (text, is_error) in self._status.items():
            if text:
                messages.append(f"{name.title()}: {text}")
                has_error |= is_error

        self.status_changed.emit(" . ".join(messages), has_error)

    @QtCore.pyqtSlot(object, object)
    def _sync_time_range(self, source, bounds):
        if self._syncing_time_range:
            return

        target = (
            self.spectrogram_plot if source is self.trace.getViewBox() else self.trace
        )

        self._syncing_time_range = True
        try:
            target.setXRange(*bounds, padding=0)
        finally:
            self._syncing_time_range = False

    def set_source(self, run, state):
        fresh = (
            run is not None
            and state.get("valid")
            and not state.get("stale")
            and not state.get("solving")
            and state.get("request_id") == run["request_id"]
        )

        preview = (
            run is not None
            and state.get("partial")
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
        elif preview:
            text = "Preview run"
        else:
            text = "Settings changed"

        if run is not None and not (fresh or preview):
            text += " - showing previous run"
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
        self._spectrum = None
        self._spectrogram = None
        self.selection_label.clear()
        self.trace.setToolTip("")
        self.region.hide()
        for widget in (self.start_spin, self.end_spin, self.full_button):
            widget.setEnabled(False)

        if self._run is None:
            self._analysis_source = None
            self._queue_analysis()
            self._interval = None
            self.curve.clear()
            self.trace.setLabel("left", "Value")
            return

        index = self.trajectory_combo.currentIndex()
        coordinate = self.coordinate_combo.currentText()
        source = (self._run["attractor"], index, coordinate)
        if source != self._analysis_source:
            self._analysis_source = source
            self._spectrum_revision += 1
            self._spectrogram_revision += 1

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
            self._queue_analysis()
            self.curve.clear()
            self.selection_label.setText(str(error))
            return

        self.curve.setData(self.signal.times, self.signal.values)
        self.trace.setLabel("left", coordinate)
        self.trace.enableAutoRange()
        self.trace.setToolTip(
            f"Record: {self.signal.values.size:,} samples\n"
            f"Sampling interval: {dt:.6g}\n"
            f"Sampling rate: {1.0 / dt:.6g} samples/unit time\n"
            f"Nyquist: {0.5 / dt:.6g} cycles/unit time"
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
            self._queue_analysis()
            return

        selected = self.selected_signal
        self.selection_label.setText(
            f"Selected: {selected.values.size:,} samples | "
            f"Time: {selected.times[0]:.9g} to {selected.times[-1]:.9g} | "
            f"Span: {selected.times[-1] - selected.times[0]:.9g}"
        )
        self._queue_analysis()

    def _region_changed(self):
        self._set_interval(*self.region.getRegion())

    def _bounds_changed(self):
        start = self.start_spin.value()
        end = self.end_spin.value()

        if start >= end:
            self.selected_signal = None
            self.selection_label.setText("Start must be before end")
            self._queue_analysis()
            return

        self._set_interval(start, end)

    def _refresh_analysis(self):
        for kind in ("spectrum", "spectrogram"):
            if (
                getattr(self, f"_{kind}_waiting")
                and getattr(self, f"_{kind}_worker") is None
            ):
                getattr(self, f"_{kind}_timer").start(0)

    def _reset_interval(self):
        if self.signal is not None:
            self._set_interval(self.signal.times[0], self.signal.times[-1])

    def _queue_analysis(self):
        self._queue_spectrum()
        self._queue_spectrogram()

    def _queue_spectrogram(self):
        if self.selected_signal is None:
            self._spectrogram_revision += 1
            self._spectrogram_waiting = False
            self._spectrogram_timer.stop()
            self._spectrogram = None
            self.spectrogram_image.clear()
            self.spectrogram_plot.setToolTip("")
            self._set_status("spectrogram")
            return

        self._spectrogram_waiting = True
        self._set_status("spectrogram", "Updating")
        if self._spectrogram_worker is None and not self._spectrogram_timer.isActive():
            self._spectrogram_timer.start()

    def _start_spectrogram(self):
        if not self._spectrogram_waiting:
            return

        if self._spectrogram_worker is not None:
            return
        if self.selected_signal is None:
            return

        self._spectrogram_waiting = False

        worker = SpectrogramWorker(
            self._spectrogram_revision,
            self.selected_signal,
            window_duration=self.duration_spin.value(),
            overlap=self.overlap_spin.value() / 100.0,
            remove_mean=self.mean_check.isChecked(),
            window=self.window_combo.currentData(),
        )
        worker.signals.finished.connect(
            self._on_spectrogram_finished,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._spectrogram_worker = worker
        QtCore.QThreadPool.globalInstance().start(worker)

    @QtCore.pyqtSlot(int, object, str)
    def _on_spectrogram_finished(self, revision, spectrogram, error):
        worker = self._spectrogram_worker
        self._spectrogram_worker = None

        if self._spectrogram_waiting:
            self._spectrogram_timer.start()

        if revision != self._spectrogram_revision:
            return

        if spectrogram is None:
            if not self._spectrogram_waiting:
                self._spectrogram = None
                self.spectrogram_image.clear()
                self._set_status(
                    "spectrogram",
                    error or "Spectrogram calculation failed",
                    error=True,
                )
            return

        self._spectrogram_dt = worker.signal.dt
        self._spectrogram = spectrogram
        self._apply_spectrogram_frequency()
        self._draw_spectrogram()

    def _apply_spectrogram_frequency(self):
        if self._spectrogram is None:
            return

        mode = self.frequency_view_combo.currentData()
        if mode == "manual":
            return

        spectrogram = self._spectrogram
        nyquist = 0.5 / self._spectrogram_dt
        upper = nyquist

        if mode == "auto":
            power_by_frequency = spectrogram.density.max(axis=1)
            peak = float(power_by_frequency.max())

            if peak > 0.0:
                # PSD values within 80 dB of the global peak
                visible = np.flatnonzero(power_by_frequency >= peak * 1e-8)
                upper = min(
                    nyquist,
                    max(
                        2.0 * spectrogram.bin_spacing,
                        float(spectrogram.frequencies[visible[-1]])
                        + spectrogram.bin_spacing,
                    ),
                )

        self._setting_spectrogram_frequency = True
        try:
            self.spectrogram_plot.setYRange(0.0, upper, padding=0)
        finally:
            self._setting_spectrogram_frequency = False

    @QtCore.pyqtSlot(object, object)
    def _spectrogram_frequency_changed(self, view, bounds):
        if self._setting_spectrogram_frequency:
            return

        with QtCore.QSignalBlocker(self.frequency_view_combo):
            self.frequency_view_combo.setCurrentIndex(
                self.frequency_view_combo.findData("manual")
            )

    def _draw_spectrogram(self):
        if self._spectrogram is None:
            return

        spectrogram = self._spectrogram
        density = spectrogram.density
        dt = self._spectrogram_dt
        time_step = spectrogram.hop_samples * dt
        frequency_step = spectrogram.bin_spacing
        frequency_count, time_count = density.shape
        coordinate = self.coordinate_combo.currentText()
        density_unit = f"{coordinate}^2 / (cycles/unit time)"
        peak = float(density.max())

        if self.colour_scale_combo.currentData() == "db":
            upper = 10.0 * float(np.log10(peak)) if peak > 0.0 else 0.0
            lower = upper - 80.0
            display = np.full_like(density, lower)
            positive = density > 0.0
            display[positive] = 10.0 * np.log10(density[positive])
            label = f"PSD (dB re 1 {density_unit})"
        else:
            lower = 0.0
            upper = peak if peak > 0.0 else 1.0
            display = density
            label = f"PSD ({density_unit})"

        self.spectrogram_image.setImage(
            display,
            autoLevels=False,
            levels=(lower, upper),
        )
        self.spectrogram_image.setRect(
            float(spectrogram.times[0]) - time_step / 2.0,
            float(spectrogram.frequencies[0]) - frequency_step / 2.0,
            time_count * time_step,
            frequency_count * frequency_step,
        )

        self.spectrogram_colour_bar.setLabel("left", label)
        self.spectrogram_colour_bar.setLevels((lower, upper))

        if self._spectrogram_waiting or self._spectrogram_worker is not None:
            self._set_status("spectrogram", "Updating")
        elif peak == 0.0:
            self._set_status("spectrogram", "All spectrogram power is zero.")
        else:
            self._set_status("spectrogram")

    def _queue_spectrum(self):
        signal = self.selected_signal
        if signal is None or signal.values.size < 4:
            self._spectrum_revision += 1
            self._spectrum_waiting = False
            self._spectrum_timer.stop()
            self._spectrum = None
            self.spectrum_curve.clear()
            self.spectrum_plot.setToolTip("")
            self._set_status("spectrum")
            if signal is not None:
                self._set_status(
                    "spectrum",
                    "Spectrum analysis requires at least four samples",
                    error=True,
                )
            return

        self._spectrum_waiting = True
        self._set_status("spectrum", "Updating")
        if self._spectrum_worker is None and not self._spectrum_timer.isActive():
            self._spectrum_timer.start()

    def _start_spectrum(self):
        if not self._spectrum_waiting:
            return

        if self._spectrum_worker is not None:
            return
        if self.selected_signal is None or self.selected_signal.values.size < 4:
            return

        self._spectrum_waiting = False

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
        worker = self._spectrum_worker
        self._spectrum_worker = None

        if self._spectrum_waiting:
            self._spectrum_timer.start()

        if revision != self._spectrum_revision:
            return

        if spectrum is None:
            if not self._spectrum_waiting:
                self._spectrum = None
                self.spectrum_curve.clear()
                self._set_status(
                    "spectrum",
                    error or "Spectrum calculation failed",
                    error=True,
                )
            return

        self._spectrum_dt = worker.signal.dt
        self._spectrum = spectrum
        self._draw_spectrum()

    def _draw_spectrum(self):
        logarithmic = self.log_check.isChecked()
        self.spectrum_plot.setLogMode(x=False, y=logarithmic)

        if self._spectrum is None:
            return

        spectrum = self._spectrum
        coordinate = self.coordinate_combo.currentText()

        if self.fft_check.isChecked():
            label = "|FFT(PSD)|"
            self.spectrum_plot.setLabel("bottom", "Conjugate time")
        else:
            label = f"PSD ({coordinate}^2) / (cycles/unit time)"
            self.spectrum_plot.setLabel("bottom", "Frequency (cycles per unit time)")

        self.spectrum_plot.setLabel("left", label)
        self.spectrum_curve.setData(spectrum.frequencies, spectrum.density)
        self.spectrum_plot.enableAutoRange()

        text = (
            f"Bin spacing: {spectrum.bin_spacing:.6g} cycles/unit time\n"
            f"Noise bandwidth: {spectrum.noise_bandwidth:.6g} cycles/unit time\n"
            f"Nyquist: {0.5 / self._spectrum_dt:.6g} cycles/unit time"
        )
        self.spectrum_plot.setToolTip(text)
        if self._spectrum_waiting or self._spectrum_worker is not None:
            self._set_status("spectrum", "Updating")
        elif logarithmic and not (spectrum.density > 0).any():
            self._set_status(
                "spectrum", "All power is zero. Switch off Log power to view it"
            )
        else:
            self._set_status("spectrum")

    def apply_theme(self):
        colours = plot_colours()
        for plot in (self.trace, self.spectrum_plot, self.spectrogram_plot):
            plot.setBackground(colours["plot_background"])
            plot.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        pen = colours["plot_pen"]
        if self._run is not None:
            index = self.trajectory_combo.currentIndex()
            pen = self._run["colours"][index] or pen

        self.curve.setPen(pg.mkPen(pen))
        self.spectrum_curve.setPen(pg.mkPen(colours["alternate_pen"]))
