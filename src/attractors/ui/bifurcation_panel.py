import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.Qt.QtCore import QThreadPool

from ..workers.bifurcation_worker import BifurcationWorker


class BifurcationZoom(QtWidgets.QWidget):
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.zoom_widget = pg.PlotWidget()
        self.region = pg.LinearRegionItem()
        self.updating = False
        self.x_bounds = None

        self.zoom_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.zoom_widget.showGrid(x=True, y=True, alpha=0.25)
        self.zoom_widget.setLabel("bottom", "Parameter value")

        self.region.setZValue(10)
        self.plot_widget.addItem(self.region, ignoreBounds=True)

        self.zoom_data = self.zoom_widget.plot(
            [], [], pen=None, symbol="o", symbolSize=0.25, symbolBrush="white"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.zoom_widget, 2)
        layout.addWidget(self.plot_widget, 1)

        self.region.sigRegionChanged.connect(self._region_changed)
        self.zoom_widget.sigXRangeChanged.connect(self._zoom_range_changed)

    def set_label(self, label):
        self.zoom_widget.setLabel("left", label)

    def set_data(self, x, y):
        self.zoom_data.setData(x, y)

        if x is None or len(x) == 0:
            self.x_bounds = None
            return

        finite = np.asarray(x)[np.isfinite(x)]
        if len(finite) == 0:
            self.x_bounds = None
            return

        x_min = float(np.min(finite))
        x_max = float(np.max(finite))
        if x_max <= x_min:
            self.x_bounds = None
            return

        old_bounds = self.x_bounds
        self.x_bounds = (x_min, x_max)
        self.region.setBounds(self.x_bounds)

        if old_bounds is None:
            self.region.setRegion((x_min, x_min + (x_max - x_min) * 0.1))
        else:
            region_min, region_max = self.region.getRegion()
            if region_max <= x_min or region_min >= x_max:
                self.region.setRegion((x_min, x_min + (x_max - x_min) * 0.1))
            else:
                self.region.setRegion((max(region_min, x_min), min(region_max, x_max)))

    def auto_range(self):
        self.plot_widget.autoRange()
        self.zoom_widget.autoRange()

    def clear(self):
        self.zoom_data.setData([], [])
        self.x_bounds = None

    def _region_changed(self):
        if self.updating:
            return

        self.updating = True
        x_min, x_max = self.region.getRegion()
        self.zoom_widget.setXRange(x_min, x_max)
        self.updating = False

    def _zoom_range_changed(self, *_args):
        if self.updating:
            return

        self.updating = True
        self.region.setRegion(self.zoom_widget.getViewBox().viewRange()[0])
        self.updating = False

    def detach_plot(self):
        self.plot_widget.removeItem(self.region)
        self.layout().removeWidget(self.plot_widget)
        self.plot_widget.setParent(None)


class BifurcationPanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self.config = None
        self.current_values = None
        self._sweep_gen = 0
        self._zoom = None
        self._plot_x = np.array([], dtype=np.float64)
        self._plot_y = np.array([], dtype=np.float64)

        self.setMinimumHeight(200)

        layout = QtWidgets.QVBoxLayout(self)

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Sweep param:"))
        self.param_combo = QtWidgets.QComboBox()
        self.param_combo.currentTextChanged.connect(self._update_defaults)
        row1.addWidget(self.param_combo)

        row1.addWidget(QtWidgets.QLabel("  Variable:"))
        self.var_combo = QtWidgets.QComboBox()
        self.var_combo.addItems(["x", "y", "z"])
        self.var_combo.currentTextChanged.connect(self._update_axis_label)
        row1.addWidget(self.var_combo)

        layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("From:"))
        self.min_spin = QtWidgets.QDoubleSpinBox()
        self.min_spin.setRange(-1e6, 1e6)
        self.min_spin.setSingleStep(0.01)
        row2.addWidget(self.min_spin)

        row2.addWidget(QtWidgets.QLabel("To:"))
        self.max_spin = QtWidgets.QDoubleSpinBox()
        self.max_spin.setRange(-1e6, 1e6)
        self.max_spin.setSingleStep(0.01)
        row2.addWidget(self.max_spin)

        row2.addWidget(QtWidgets.QLabel("Steps:"))
        self.steps_spin = QtWidgets.QSpinBox()
        self.steps_spin.setRange(10, 10000)
        self.steps_spin.setValue(500)
        row2.addWidget(self.steps_spin)

        row2.addWidget(QtWidgets.QLabel("Transient:"))
        self.transient_spin = QtWidgets.QDoubleSpinBox()
        self.transient_spin.setRange(0.0, 0.99)
        self.transient_spin.setSingleStep(0.05)
        self.transient_spin.setValue(0.85)
        row2.addWidget(self.transient_spin)
        layout.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("\u25b6 Run")
        self.run_btn.clicked.connect(self._run_sweep)
        row3.addWidget(self.run_btn)

        self.cancel_btn = QtWidgets.QPushButton("\u25a0 Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_sweep)
        row3.addWidget(self.cancel_btn)

        self.export_btn = QtWidgets.QPushButton("Export PNG...")
        self.export_btn.clicked.connect(self._export_plot)
        row3.addWidget(self.export_btn)

        self.zoom_check = QtWidgets.QCheckBox("ROI")
        self.zoom_check.toggled.connect(self._set_zoom_enabled)
        row3.addWidget(self.zoom_check)

        layout.addLayout(row3)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.plot_widget.setBackground("k")
        self.plot_widget.setLabel("bottom", "Parameter value")
        self.plot_widget.setLabel("left", "x")
        self.plot_data = self.plot_widget.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=0.25,
            symbolBrush=(255, 255, 255),
        )

        self.plot_layout = QtWidgets.QVBoxLayout()
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_layout.setSpacing(0)
        self.plot_layout.addWidget(self.plot_widget)

        layout.addLayout(self.plot_layout, 1)

    def _update_defaults(self):
        if self.config is None:
            return

        param_name = self.param_combo.currentText()
        if not param_name:
            return

        p = next(
            (p for p in self.config.params if p.name == param_name),
            None,
        )
        if p is None:
            return

        span = p.max_val - p.min_val
        self.min_spin.setValue(p.min_val + 0.01 * span)
        self.max_spin.setValue(p.max_val - 0.01 * span)
        self._update_axis_label()

    def _update_axis_label(self):
        label = self.var_combo.currentText()
        self.plot_widget.setLabel("left", label)
        if self._zoom is not None:
            self._zoom.set_label(label)

    def _set_zoom_enabled(self, enabled):
        if enabled and self._zoom is None:
            self.plot_layout.removeWidget(self.plot_widget)
            self._zoom = BifurcationZoom(self.plot_widget)
            self._zoom.set_label(self.var_combo.currentText())

            x, y = self._plot_x, self._plot_y
            if len(x) == 0:
                current_x, current_y = self.plot_data.getData()
                if current_x is not None and current_y is not None:
                    x, y = current_x, current_y
                    self._plot_x = np.asarray(x, dtype=np.float64)
                    self._plot_y = np.asarray(y, dtype=np.float64)

            self._zoom.set_data(x, y)
            self.plot_layout.addWidget(self._zoom)

        elif not enabled and self._zoom is not None:
            zoom = self._zoom
            self._zoom = None

            zoom.detach_plot()
            zoom.setParent(None)

            self.plot_layout.addWidget(self.plot_widget)
            self.plot_widget.show()

    def _set_plot_data(self, x, y):
        self._plot_x = np.asarray(x, dtype=np.float64)
        self._plot_y = np.asarray(y, dtype=np.float64)
        self.plot_data.setData(self._plot_x, self._plot_y)

        if self._zoom is not None:
            self._zoom.set_data(self._plot_x, self._plot_y)

    def set_config(self, config, current_values):
        self.cancel_sweep()
        self._sweep_gen += 1
        self._error_label.setVisible(False)
        self.config = config
        self.current_values = current_values

        self.param_combo.blockSignals(True)
        self.param_combo.clear()
        self.param_combo.addItems([p.name for p in config.params])
        self.param_combo.blockSignals(False)

        # self.plot_data.setData([], [])
        self._set_plot_data([], [])
        if self._zoom is not None:
            self._zoom.clear()

        has_params = bool(config.params)
        self.run_btn.setEnabled(has_params)
        self.param_combo.setEnabled(has_params)
        self.min_spin.setEnabled(has_params)
        self.max_spin.setEnabled(has_params)
        self.steps_spin.setEnabled(has_params)
        self.transient_spin.setEnabled(has_params)

        if not has_params:
            self._error_label.setText("No parameters available to sweep")
            self._error_label.setVisible(True)
            return

        self._update_defaults()

    def _run_sweep(self):
        if self.config is None:
            return
        param_name = self.param_combo.currentText()
        min_val = self.min_spin.value()
        max_val = self.max_spin.value()
        steps = self.steps_spin.value()
        transient = self.transient_spin.value()
        axis = self.var_combo.currentIndex()

        param_values = np.linspace(min_val, max_val, steps)
        base_params = {k: v for k, v in self.current_values.items() if k != param_name}

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._error_label.setVisible(False)
        self.run_btn.setText("\u25b6 Run")
        self._sweep_gen += 1
        gen = self._sweep_gen

        t_max = self.config.time_defaults.t_max * 4
        t_min = self.config.time_defaults.t_min
        n = self.config.time_defaults.n

        worker = BifurcationWorker(
            self.config,
            base_params,
            param_name,
            param_values,
            n,
            transient,
            axis,
            t_max,
            t_min,
        )
        worker.signals.chunk_ready.connect(
            lambda vals, peaks, g=gen: self._on_chunk_ready(vals, peaks, g)
        )
        worker.signals.finished.connect(lambda g=gen: self._on_worker_finished(g))
        worker.signals.error.connect(lambda msg, g=gen: self._on_worker_error(msg, g))
        worker.signals.progress.connect(self.progress.setValue)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def cancel_sweep(self):
        if self._worker:
            self._worker.cancel()
            self._worker = None
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_chunk_ready(self, vals, peaks_list, gen):
        if gen != self._sweep_gen:
            return

        if not peaks_list:
            self._set_plot_data([], [])
            return

        lens = [len(p) for p in peaks_list]
        if sum(lens) == 0:
            self._set_plot_data([], [])
            return

        x = np.repeat(vals, lens)
        y = np.concatenate(peaks_list)
        self._set_plot_data(x, y)

    def _on_worker_finished(self, gen):
        if gen != self._sweep_gen:
            return
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        self._worker = None

    def _on_worker_error(self, msg, gen):
        if gen != self._sweep_gen:
            return
        self._error_label.setText(f"Error: {msg}")
        self._error_label.setVisible(True)
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)
        self._worker = None

    def _export_plot(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export bifurcation diagram",
            "",
            "PNG (*.png)",
        )
        if path:
            exporter = ImageExporter(self.plot_widget.plotItem)
            exporter.export(path)
