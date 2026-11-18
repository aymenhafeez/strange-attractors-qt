# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import functools

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import (
    power_spectral_density,
    power_spectrogram,
    select_interval,
    trajectory_signal,
)
from ..workers.signal_worker import SignalWorker
from .style import SIGNAL_PANEL, SIGNAL_PLOTS, plot_colours


class _AnalysisJob(QtCore.QObject):
    def __init__(self, make_worker, on_ready, on_failed, parent):
        super().__init__(parent)
        self._make_worker = make_worker
        self._on_ready = on_ready
        self._on_failed = on_failed
        self._revision = 0
        self._waiting = False
        self._worker = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start)

    def busy(self):
        return self._waiting or self._worker is not None

    def queue(self):
        self._waiting = True
        if self._worker is None and not self._timer.isActive():
            self._timer.start()

    def cancel(self):
        self._revision += 1
        self._waiting = False
        self._timer.stop()

    def _start(self):
        # only run the timer when waiting with no worker is prcoess
        self._waiting = False
        self._worker = self._make_worker(self._revision)
        self._worker.signals.finished.connect(
            self._finished, QtCore.Qt.ConnectionType.QueuedConnection
        )
        QtCore.QThreadPool.globalInstance().start(self._worker)

    @QtCore.pyqtSlot(int, object, str)
    def _finished(self, revision, result, error):
        worker, self._worker = self._worker, None
        if self._waiting:
            self._timer.start()
        if revision != self._revision:
            return

        if result is None:
            # failure gets renewed by a newer queue
            if not self._waiting:
                self._on_failed(error)
        else:
            self._on_ready(worker, result)


def _plot_area(header, plot):
    area = QtWidgets.QFrame()
    area.setObjectName("panelSurface")
    area.setStyleSheet(SIGNAL_PLOTS)
    area.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
    layout = QtWidgets.QVBoxLayout(area)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(header)
    layout.addWidget(plot, 1)

    return area


class SignalPanel(QtWidgets.QWidget):
    status_changed = QtCore.pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = {
            "selection": ("", False),
            "spectrum": ("", False),
            "spectrogram": ("", False),
        }
        self._run = None
        self.signal = None
        self.selected_signal = None
        self._interval = None
        self._analysis_source = None
        self._spectrum_dt = None
        self._spectrogram_dt = None
        self._spectrum = None
        self._syncing_time_range = False
        self._spectrogram = None
        self._setting_spectrogram_frequency = False

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(SIGNAL_PANEL)

        self.trajectory_combo = QtWidgets.QComboBox()
        self.coordinate_combo = QtWidgets.QComboBox()
        self.trajectory_combo.setEnabled(False)
        self.coordinate_combo.setEnabled(False)

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
        self.colour_scale_combo.setCurrentIndex(1)

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

        self._spectrum_job = _AnalysisJob(
            self._spectrum_worker,
            self._on_spectrum_ready,
            self._on_spectrum_failed,
            self,
        )
        self._spectrogram_job = _AnalysisJob(
            self._spectrogram_worker,
            self._on_spectrogram_ready,
            self._on_spectrogram_failed,
            self,
        )

        self.duration_spin.valueChanged.connect(self._queue_spectrogram)
        self.overlap_spin.valueChanged.connect(self._queue_spectrogram)
        self.colour_scale_combo.currentIndexChanged.connect(self._draw_spectrogram)

        self.mean_check.toggled.connect(self._queue_analysis)
        self.window_combo.currentIndexChanged.connect(self._queue_analysis)
        self.log_check.toggled.connect(self._draw_spectrum)

        self.trajectory_combo.setMinimumContentsLength(18)
        self.trajectory_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )

        self.colour_scale_combo.setAccessibleName("Spectrogram colour scale")

        right = QtCore.Qt.AlignmentFlag.AlignRight
        left = QtCore.Qt.AlignmentFlag.AlignLeft
        controls = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(controls)
        grid.setContentsMargins(5, 5, 5, 0)
        left = QtCore.Qt.AlignmentFlag.AlignLeft
        grid.addWidget(QtWidgets.QLabel("Trajectory:"), 0, 0, right)
        grid.addWidget(self.trajectory_combo, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Coordinate:"), 1, 0, right)
        grid.addWidget(self.coordinate_combo, 1, 1, left)

        grid.addWidget(QtWidgets.QLabel("Start:"), 0, 3, right)
        grid.addWidget(self.start_spin, 0, 4)
        grid.addWidget(QtWidgets.QLabel("End:"), 1, 3, right)
        grid.addWidget(self.end_spin, 1, 4)
        grid.addWidget(self.full_button, 0, 5)

        grid.addWidget(QtWidgets.QLabel("Window:"), 0, 7, right)
        grid.addWidget(self.window_combo, 0, 8, left)
        grid.addWidget(self.mean_check, 1, 8)

        grid.setColumnMinimumWidth(2, 12)
        grid.setColumnMinimumWidth(6, 12)
        grid.setColumnStretch(9, 1)

        spectrum_header = QtWidgets.QWidget()
        spectrum_row = QtWidgets.QHBoxLayout(spectrum_header)
        spectrum_row.setContentsMargins(3, 0, 0, 0)
        spectrum_row.addWidget(self.log_check)
        spectrum_row.addStretch(1)

        spectrogram_header = QtWidgets.QWidget()
        spectrogram_row = QtWidgets.QHBoxLayout(spectrogram_header)
        spectrogram_row.setContentsMargins(3, 0, 3, 0)
        spectrogram_row.setSpacing(1)
        spectrogram_row.addWidget(QtWidgets.QLabel("Duration:"))
        spectrogram_row.addWidget(self.duration_spin)
        spectrogram_row.addWidget(QtWidgets.QLabel("Overlap:"))
        spectrogram_row.addWidget(self.overlap_spin, alignment=left)
        spectrogram_row.addWidget(self.frequency_view_combo)
        spectrogram_row.addWidget(self.colour_scale_combo)

        time_area = _plot_area(controls, self.trace)
        spectrum_area = _plot_area(spectrum_header, self.spectrum_plot)
        spectrogram_area = _plot_area(spectrogram_header, self.spectrogram_plot)

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

        self.status_changed.emit(", ".join(messages), has_error)

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

    def set_source(self, run):
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
                for label, spec in zip(run.labels, run.trajectory_specs):
                    initial = ", ".join(f"{v:g}" for v in spec["ic"])
                    self.trajectory_combo.addItem(f"{label}: ({initial})")

                self.trajectory_combo.setCurrentIndex(
                    min(trajectory, self.trajectory_combo.count() - 1)
                )
                self.coordinate_combo.addItems(run.variables)
                self.coordinate_combo.setCurrentText(
                    coordinate if coordinate in run.variables else run.variables[0]
                )
                parameters = ", ".join(
                    f"{name}={value:g}" for name, value in run.parameters.items()
                )
                self.trajectory_combo.setToolTip(f"{run.attractor}\n{parameters}")
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
        self._set_status("selection")
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
        source = (self._run.attractor, index, coordinate)
        if source != self._analysis_source:
            self._analysis_source = source
            self._spectrum_job.cancel()
            self._spectrogram_job.cancel()

        self.signal = trajectory_signal(
            self._run.solutions[index],
            self._run.variables.index(coordinate),
            t_min=self._run.t_min,
            t_max=self._run.trajectory_specs[index]["t_max"],
        )
        dt = self.signal.dt

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
            self._set_status("selection", str(error), error=True)
            self._queue_analysis()
            return

        self._set_status("selection")
        self._queue_analysis()

    def _region_changed(self):
        self._set_interval(*self.region.getRegion())

    def _bounds_changed(self):
        start = self.start_spin.value()
        end = self.end_spin.value()

        # swapMode="block" covers the region lines being dragged past each other but
        # still need to cover the spinboxes
        if start >= end:
            self.selected_signal = None
            self._set_status("selection", "Start must be before end", error=True)
            self._queue_analysis()
            return

        self._set_interval(start, end)

    def _reset_interval(self):
        if self.signal is not None:
            self._set_interval(self.signal.times[0], self.signal.times[-1])

    def _queue_analysis(self):
        self._queue_spectrum()
        self._queue_spectrogram()

    def _queue_spectrogram(self):
        if self.selected_signal is None:
            self._spectrogram_job.cancel()
            self._spectrogram = None
            self.spectrogram_image.clear()
            self.spectrogram_plot.setToolTip("")
            self._set_status("spectrogram")
            return

        self._spectrogram_job.queue()
        self._set_status("spectrogram", "Updating")

    def _spectrogram_worker(self, revision):
        compute = functools.partial(
            power_spectrogram,
            window_duration=self.duration_spin.value(),
            overlap=self.overlap_spin.value() / 100.0,
            remove_mean=self.mean_check.isChecked(),
            window=self.window_combo.currentData(),
        )
        return SignalWorker(revision, self.selected_signal, compute)

    def _on_spectrogram_ready(self, worker, spectrogram):
        self._spectrogram_dt = worker.signal.dt
        self._spectrogram = spectrogram
        self._apply_spectrogram_frequency()
        self._draw_spectrogram()

    def _on_spectrogram_failed(self, error):
        self._spectrogram = None
        self.spectrogram_image.clear()
        self._set_status("spectrogram", error, error=True)

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

        if self._spectrogram_job.busy():
            self._set_status("spectrogram", "Updating")
        elif peak == 0.0:
            self._set_status("spectrogram", "All spectrogram power is zero.")
        else:
            self._set_status("spectrogram")

    def _queue_spectrum(self):
        signal = self.selected_signal
        if signal is None or signal.values.size < 4:
            self._spectrum_job.cancel()
            self._spectrum = None
            self.spectrum_curve.clear()
            self.spectrum_plot.setToolTip("")
            if signal is None:
                self._set_status("spectrum")
            else:
                self._set_status(
                    "spectrum",
                    "Spectrum analysis requires at least four samples",
                    error=True,
                )
            return

        self._spectrum_job.queue()
        self._set_status("spectrum", "Updating")

    def _spectrum_worker(self, revision):
        compute = functools.partial(
            power_spectral_density,
            remove_mean=self.mean_check.isChecked(),
            window=self.window_combo.currentData(),
        )
        return SignalWorker(revision, self.selected_signal, compute)

    def _on_spectrum_ready(self, worker, spectrum):
        self._spectrum_dt = worker.signal.dt
        self._spectrum = spectrum
        self._draw_spectrum()

    def _on_spectrum_failed(self, error):
        self._spectrum = None
        self.spectrum_curve.clear()
        self._set_status("spectrum", error, error=True)

    def _draw_spectrum(self):
        logarithmic = self.log_check.isChecked()
        self.spectrum_plot.setLogMode(x=False, y=logarithmic)

        if self._spectrum is None:
            return

        spectrum = self._spectrum
        coordinate = self.coordinate_combo.currentText()

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
        if self._spectrum_job.busy():
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
            pen = self._run.colours[index] or pen

        self.curve.setPen(pg.mkPen(pen))
        self.spectrum_curve.setPen(pg.mkPen(colours["alternate_pen"]))
