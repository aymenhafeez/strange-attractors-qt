# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.Qt.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from ..core.sections import axis_index, plane_crossings, stroboscopic_samples
from ..core.solution_validation import validate_solutions
from ..core.solver import solve_attractor
from .style import PANEL_SURFACE, plot_colours

DIR_MAP = {"both": "both", "rising": "positive", "falling": "negative"}
N_BINS = 96
SLIDER_STEPS = 1000


class _PoincareSignals(QObject):
    result_ready = pyqtSignal(object)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class _PoincareWorker(QRunnable):
    def __init__(self, config, values, n, t_max):
        super().__init__()
        self.config = config
        self.values = values
        self.n = n
        self.t_max = t_max
        self.signals = _PoincareSignals()
        self._cancel = False

    def run(self):
        try:
            sol = solve_attractor(self.config, self.values, self.n, t_max=self.t_max)
            if not self._cancel:
                self.signals.result_ready.emit(sol)
        except Exception as exc:  # noqa: BLE001
            if not self._cancel:
                self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self._cancel = True


class PoincarePanel(QtWidgets.QWidget):
    plane_changed = QtCore.pyqtSignal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._solutions = None
        self._solution_t_max = None
        self._config = None
        self._values = None
        self._worker = None
        self._solve_gen = 0
        self._value_bounds = None

        self.setMinimumHeight(120)
        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_SURFACE)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        solve_row = QtWidgets.QHBoxLayout()
        solve_row.setSpacing(8)

        self.solve_btn = QtWidgets.QPushButton("Run")
        self.solve_btn.clicked.connect(self._start_solve)
        solve_row.addWidget(self.solve_btn)

        self.auto_check = QtWidgets.QCheckBox("Auto")
        self.auto_check.setChecked(True)
        self.auto_check.setToolTip("Auto solve when attractor parameters change")
        solve_row.addWidget(self.auto_check)

        self.heatmap_check = QtWidgets.QCheckBox("Heatmap")
        self.heatmap_check.setChecked(True)
        solve_row.addWidget(self.heatmap_check)

        self.dropdown = QtWidgets.QComboBox()
        colourmaps = pg.colormap.listMaps(source="matplotlib")
        self.dropdown.addItems(colourmaps)
        self.dropdown.setCurrentText(plot_colours()["cmap"])
        self.dropdown.currentTextChanged.connect(self._update_colourmap)
        self.dropdown.setMaxVisibleItems(12)
        self.dropdown.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self.dropdown.setMinimumWidth(180)
        solve_row.addWidget(QtWidgets.QLabel("Map:"))
        solve_row.addWidget(self.dropdown)

        self.planar_view_combo = QtWidgets.QComboBox()
        self.planar_view_combo.addItems(
            ["Crossing index", "Return map", "Return interval"]
        )
        self.planar_view_combo.currentTextChanged.connect(self.recompute)
        self.planar_view_combo.hide()
        solve_row.addWidget(self.planar_view_combo)

        solve_row.addStretch(1)
        layout.addLayout(solve_row)

        ctrl_row = QtWidgets.QHBoxLayout()
        ctrl_row.setSpacing(8)

        self.tmax_spin = QtWidgets.QDoubleSpinBox()
        self.tmax_spin.setRange(1, 100000)
        self.tmax_spin.setSingleStep(100)
        self.tmax_spin.setDecimals(0)
        self.tmax_spin.setValue(500)
        self.tmax_spin.setFixedWidth(88)
        ctrl_row.addWidget(QtWidgets.QLabel("t_max:"))
        ctrl_row.addWidget(self.tmax_spin)

        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1000, 10000000)
        self.n_spin.setSingleStep(1000)
        self.n_spin.setValue(100000)
        self.n_spin.setFixedWidth(112)
        ctrl_row.addWidget(QtWidgets.QLabel("n:"))
        ctrl_row.addWidget(self.n_spin)

        self.plane_combo = QtWidgets.QComboBox()
        self.plane_combo.addItems(["x", "y", "z"])
        self.plane_combo.setFixedWidth(58)
        ctrl_row.addWidget(QtWidgets.QLabel("Plane:"))
        ctrl_row.addWidget(self.plane_combo)

        self.dir_combo = QtWidgets.QComboBox()
        self.dir_combo.addItems(["both", "rising", "falling"])
        self.dir_combo.setFixedWidth(92)
        ctrl_row.addWidget(QtWidgets.QLabel("Dir:"))
        ctrl_row.addWidget(self.dir_combo)

        self.value_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.value_slider.setRange(0, SLIDER_STEPS)
        self.value_slider.setEnabled(False)
        self.value_slider.setFixedWidth(240)
        self.value_slider.valueChanged.connect(self._on_slider_changed)
        ctrl_row.addWidget(self.value_slider)

        self.value_spin = QtWidgets.QDoubleSpinBox()
        self.value_spin.setRange(-1000, 1000)
        self.value_spin.setSingleStep(0.5)
        self.value_spin.setDecimals(3)
        self.value_spin.setFixedWidth(88)
        ctrl_row.addWidget(QtWidgets.QLabel("Value:"))
        ctrl_row.addWidget(self.value_spin)

        ctrl_row.addStretch(1)
        layout.addLayout(ctrl_row)

        self.sampling_controls = QtWidgets.QWidget()
        sampling_layout = QtWidgets.QHBoxLayout(self.sampling_controls)

        self.transient_spin = QtWidgets.QDoubleSpinBox()
        self.transient_spin.setRange(0, 99)
        self.transient_spin.setSuffix("%")
        self.transient_spin.setValue(20)
        self.transient_spin.setKeyboardTracking(False)

        sampling_layout.addWidget(QtWidgets.QLabel("Discard"))
        sampling_layout.addWidget(self.transient_spin)
        self.transient_spin.valueChanged.connect(self.recompute)

        sampling_layout.setContentsMargins(0, 0, 0, 0)

        self.section_mode_combo = QtWidgets.QComboBox()
        self.section_mode_combo.addItems(["Line", "Stroboscopic"])

        self.period_spin = QtWidgets.QDoubleSpinBox()
        self.period_spin.setDecimals(6)
        self.period_spin.setRange(0.000001, 1000000)
        self.period_spin.setValue(2 * np.pi)
        self.period_spin.setKeyboardTracking(False)
        self.period_spin.setSingleStep(0.1)

        self.phase_spin = QtWidgets.QDoubleSpinBox()
        self.phase_spin.setDecimals(6)
        self.phase_spin.setRange(-1000000, 1000000)
        self.phase_spin.setKeyboardTracking(False)

        sampling_layout.addWidget(self.section_mode_combo)
        sampling_layout.addWidget(QtWidgets.QLabel("Period:"))
        sampling_layout.addWidget(self.period_spin)
        sampling_layout.addWidget(QtWidgets.QLabel("Phase time:"))
        sampling_layout.addWidget(self.phase_spin)
        layout.addWidget(self.sampling_controls)

        self.section_mode_combo.currentTextChanged.connect(
            self._on_section_mode_changed
        )
        self.period_spin.valueChanged.connect(self.recompute)
        self.phase_spin.valueChanged.connect(self.recompute)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(
            x=True, y=True, alpha=plot_colours()["plot_grid_alpha"]
        )
        self.plot_widget.setBackground(plot_colours()["plot_background"])
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.getPlotItem().setContentsMargins(0, 10, 0, 0)
        layout.addWidget(self.plot_widget)

        self._scatter = self.plot_widget.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=1,
            symbolBrush=plot_colours()["scatter_brush"],
        )

        self._img = pg.ImageItem()
        selected_cmap = self.dropdown.currentText()
        cmap = pg.colormap.get(selected_cmap, source="matplotlib")
        self._colourbar = self.plot_widget.getPlotItem().addColorBar(
            self._img, colorMap=cmap, values=(0, 10), width=20
        )
        self._colourbar.setVisible(False)
        self._img.setLookupTable(cmap.getLookupTable())
        self._img.setVisible(False)
        self.plot_widget.addItem(self._img)

        self.plane_combo.currentTextChanged.connect(self._on_plane_changed)
        self.value_spin.editingFinished.connect(self._on_value_changed)
        self.dir_combo.currentTextChanged.connect(self.recompute)
        self.heatmap_check.toggled.connect(self._on_mode_changed)

        self._on_plane_changed(self.plane_combo.currentText())

    def set_attractor(self, config, values):
        old_dimension = self._config.dimension if self._config else None
        previous_axis = self.plane_combo.currentText()

        self.clear()
        self._config = config
        self._values = dict(values)
        self.setEnabled(True)

        axis = (
            previous_axis if previous_axis in config.variables else config.variables[0]
        )

        with QtCore.QSignalBlocker(self.plane_combo):
            self.plane_combo.clear()
            self.plane_combo.addItems(config.variables)
            self.plane_combo.setCurrentText(axis)

        is_2d = config.dimension == 2
        self.planar_view_combo.setVisible(is_2d)
        self.sampling_controls.setVisible(is_2d)

        if is_2d and old_dimension != 2:
            self.dir_combo.setCurrentText("rising")

        self._on_plane_changed(axis)
        self._on_section_mode_changed()

        if self.auto_check.isChecked():
            self._start_solve()

    def _transient_cutoff(self):
        start = self._config.time_defaults.t_min
        duration = self._solution_t_max - start
        return start + self.transient_spin.value() / 100 * duration

    def _set_solve_enabled(self, enabled):
        self.solve_btn.setEnabled(enabled)
        self.tmax_spin.setEnabled(enabled)
        self.n_spin.setEnabled(enabled)

    def _start_solve(self):
        if self._config is None:
            return
        self.cancel_solve()
        self._set_solve_enabled(False)
        self._error_label.setVisible(False)
        self._solve_gen += 1
        gen = self._solve_gen

        t_max = self.tmax_spin.value()
        n = self.n_spin.value()
        worker = _PoincareWorker(self._config, self._values, n, t_max)
        worker.signals.result_ready.connect(
            lambda sol, g=gen, end=t_max: self._on_solve_result(sol, g, end)
        )
        worker.signals.finished.connect(lambda g=gen: self._on_solve_finished(g))
        worker.signals.error.connect(lambda msg, g=gen: self._on_solve_error(msg, g))
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def cancel_solve(self):
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None

    def _on_solve_result(self, sol, gen, t_max):
        if gen != self._solve_gen:
            return

        is_valid, message = validate_solutions([sol], dimension=self._config.dimension)
        if not is_valid:
            self._solutions = None
            self._clear_plot_data()
            self._show_error(message)
            return

        self._solutions = [sol]
        self._solution_t_max = t_max
        plane = self.plane_combo.currentText()
        col = axis_index(plane)
        midpoint = (sol[:, col].max() + sol[:, col].min()) / 2
        self._set_value_bounds(plane)
        self._set_value(midpoint)
        self._on_section_mode_changed()

    def _on_solve_finished(self, gen):
        if gen != self._solve_gen:
            return
        self._set_solve_enabled(True)
        self._worker = None

    def _on_solve_error(self, msg, gen):
        if gen != self._solve_gen:
            return
        self._solutions = None
        self._clear_plot_data()
        self._show_error(msg)
        self._set_solve_enabled(True)
        self._worker = None

    def _show_error(self, message):
        self._error_label.setText(f"Error: {message}")
        self._error_label.setVisible(True)

    def _clear_plot_data(self):
        self._value_bounds = None
        self.value_slider.setEnabled(False)
        self._scatter.setData([], [])
        self._img.setVisible(False)
        self._colourbar.setVisible(False)

    def _is_stroboscopic(self):
        return (
            self._config is not None
            and self._config.dimension == 2
            and self.section_mode_combo.currentText() == "Stroboscopic"
        )

    def _emit_plane(self):
        if not self.isVisible():
            return

        stroboscopic = self._is_stroboscopic()
        if stroboscopic:
            self.plane_changed.emit("", 0.0)
        else:
            self.plane_changed.emit(
                self.plane_combo.currentText(), self.value_spin.value()
            )

    def _on_plane_changed(self, plane):
        variables = (
            self._config.variables if self._config is not None else ("x", "y", "z")
        )
        remaining = tuple(name for name in variables if name != plane)

        if len(remaining) == 1:
            lh, lv = "Crossing", remaining[0].upper()
        else:
            lh, lv = (name.upper() for name in remaining)

        self.plot_widget.setLabel("bottom", lh)
        self.plot_widget.setLabel("left", lv)

        self._value_bounds = None

        if self._solutions:
            col = axis_index(plane)
            values = self._solutions[0][:, col]
            midpoint = (values.max() + values.min()) / 2
            self._set_value_bounds(plane)
            self._set_value(midpoint)
            return

        self.value_slider.setEnabled(False)
        self._emit_plane()
        self.recompute()

    def _recompute_planar(self, plane, value, direction):
        coordinate = next(name for name in self._config.variables if name != plane)
        mode = self.planar_view_combo.currentText()
        horizontal = []
        vertical = []

        for solution in self._solutions:
            times = np.linspace(
                self._config.time_defaults.t_min,
                self._solution_t_max,
                len(solution) + 1,
            )
            points = np.vstack((self._config.initial_conditions, solution))
            crossings = plane_crossings(
                points, plane, value, direction=direction, times=times
            )
            (values,) = crossings.section_coordinates()
            keep = crossings.times >= self._transient_cutoff()
            values = values[keep]
            crossing_times = crossings.times[keep]

            if mode == "Return map":
                x = values[:-1]
                y = values[1:]
                bottom = f"{coordinate}ₙ"
                left = f"{coordinate}ₙ₊₁"
            elif mode == "Return interval":
                x = np.arange(1, len(values))
                y = np.diff(crossing_times)
                bottom = "Crossing"
                left = "Return interval"
            else:
                x = np.arange(len(values))
                y = values
                bottom = "Crossing"
                left = coordinate

            horizontal.append(x)
            vertical.append(y)

        self._img.hide()
        self._colourbar.hide()
        self._scatter.show()
        self._scatter.setData(np.concatenate(horizontal), np.concatenate(vertical))
        self.plot_widget.setLabel("bottom", bottom)
        self.plot_widget.setLabel("left", left)
        self.plot_widget.autoRange()

    def _on_value_changed(self):
        self._sync_slider_to_value(self.value_spin.value())
        self._emit_plane()
        self.recompute()

    def _on_slider_changed(self, slider_value):
        if self._value_bounds is None:
            return

        self._set_value(self._slider_to_value(slider_value))

    def _set_value(self, value):
        self.value_spin.blockSignals(True)
        self.value_spin.setValue(value)
        self.value_spin.blockSignals(False)
        self._sync_slider_to_value(self.value_spin.value())
        self._emit_plane()
        self.recompute()

    def _set_value_bounds(self, plane):
        bounds = self._axis_bounds(plane)
        if bounds is None:
            self._value_bounds = None
            self.value_slider.setEnabled(False)
            return

        minimum, maximum = bounds
        self._value_bounds = bounds
        self.value_spin.setRange(minimum, maximum)
        self.value_spin.setSingleStep((maximum - minimum) / 100)
        self.value_slider.setEnabled(True)

    def _axis_bounds(self, plane):
        if not self._solutions:
            return None

        col = axis_index(plane)
        values = []
        for sol in self._solutions:
            axis_values = np.asarray(sol)[:, col]
            finite = axis_values[np.isfinite(axis_values)]
            if len(finite) > 0:
                values.append(finite)

        if not values:
            return None

        all_values = np.concatenate(values)
        minimum = float(all_values.min())
        maximum = float(all_values.max())
        if minimum == maximum:
            pad = 0.5 if minimum == 0 else abs(minimum) * 0.05
            minimum -= pad
            maximum += pad

        return minimum, maximum

    def _sync_slider_to_value(self, value):
        if self._value_bounds is None:
            return

        self.value_slider.blockSignals(True)
        self.value_slider.setValue(self._value_to_slider(value))
        self.value_slider.blockSignals(False)

    def _value_to_slider(self, value):
        minimum, maximum = self._value_bounds
        if maximum == minimum:
            return 0

        ratio = (float(value) - minimum) / (maximum - minimum)
        return round(np.clip(ratio, 0.0, 1.0) * SLIDER_STEPS)

    def _slider_to_value(self, slider_value):
        minimum, maximum = self._value_bounds
        ratio = float(slider_value) / SLIDER_STEPS
        return minimum + ratio * (maximum - minimum)

    def _on_mode_changed(self):
        heatmap = self.heatmap_check.isChecked()
        self._scatter.setVisible(not heatmap)
        self._img.setVisible(heatmap)
        self._colourbar.setVisible(heatmap)
        self.recompute()

    def recompute(self):
        if self._solutions is None:
            return
        self._error_label.hide()

        plane = self.plane_combo.currentText()
        value = self.value_spin.value()
        direction = DIR_MAP[self.dir_combo.currentText()]

        if self._config.dimension == 2 and not self._is_stroboscopic():
            self._recompute_planar(plane, value, direction)
            return

        all_h = []
        all_v = []

        for sol in self._solutions:
            if self._is_stroboscopic():
                times = np.linspace(
                    self._config.time_defaults.t_min,
                    self._solution_t_max,
                    len(sol) + 1,
                )
                points = np.vstack((self._config.initial_conditions, sol))
                sample_times, samples = stroboscopic_samples(
                    points,
                    times,
                    self.period_spin.value(),
                    self.phase_spin.value(),
                )
                samples = samples[sample_times >= self._transient_cutoff()]
                h, v = samples[:, 0], samples[:, 1]
                self.plot_widget.setLabel("bottom", "X")
                self.plot_widget.setLabel("left", "Y")
            else:
                crossings = plane_crossings(sol, plane, value, direction=direction)
                h, v = crossings.section_coordinates()

            all_h.append(h)
            all_v.append(v)

        h_all = np.concatenate(all_h) if all_h else np.array([], dtype=np.float64)
        v_all = np.concatenate(all_v) if all_v else np.array([], dtype=np.float64)

        if self.heatmap_check.isChecked():
            self._scatter.setData([], [])
            if len(h_all) > 0:
                heatmap, xedges, yedges = np.histogram2d(h_all, v_all, bins=N_BINS)
                self._img.setImage(np.log1p(heatmap))
                self._img.setRect(
                    QtCore.QRectF(
                        xedges[0],
                        yedges[0],
                        xedges[-1] - xedges[0],
                        yedges[-1] - yedges[0],
                    )
                )
                self._img.setVisible(True)
                self._colourbar.setVisible(True)
                self.plot_widget.autoRange()
                return
            self._img.setVisible(False)
            self._colourbar.setVisible(False)
        else:
            self._img.setVisible(False)
            self._colourbar.setVisible(False)
            if len(h_all) > 0:
                self._scatter.setData(h_all, v_all)
                self.plot_widget.autoRange()
                return
            self._scatter.setData([], [])

    def _on_section_mode_changed(self):
        stroboscopic = self._is_stroboscopic()
        is_2d = self._config is not None and self._config.dimension == 2

        self.period_spin.setEnabled(stroboscopic)
        self.phase_spin.setEnabled(stroboscopic)
        self.plane_combo.setEnabled(not stroboscopic)
        self.dir_combo.setEnabled(not stroboscopic)
        self.value_spin.setEnabled(not stroboscopic)
        self.value_slider.setEnabled(
            not stroboscopic and self._value_bounds is not None
        )
        self.planar_view_combo.setEnabled(not stroboscopic)
        self.heatmap_check.setEnabled(not is_2d or stroboscopic)
        self.plot_widget.setAspectLocked(not is_2d or stroboscopic)

        self._emit_plane()
        self.recompute()

    def _update_colourmap(self, cmap_name):
        cmap = pg.colormap.get(cmap_name, source="matplotlib")
        self._img.setLookupTable(cmap.getLookupTable())
        self._colourbar.setColorMap(cmap)

    def clear(self):
        self.cancel_solve()
        self._solve_gen += 1
        self._config = None
        self._values = None
        self._solutions = None
        self._solution_t_max = None
        self._set_solve_enabled(True)
        self._clear_plot_data()
        self._error_label.hide()

    def apply_theme(self):
        self.plot_widget.setBackground(plot_colours()["plot_background"])
        self.plot_widget.showGrid(
            x=True, y=True, alpha=plot_colours()["plot_grid_alpha"]
        )
        self._scatter.setData(symbolBrush=plot_colours()["scatter_brush"])
        self.dropdown.setCurrentText(plot_colours()["cmap"])
