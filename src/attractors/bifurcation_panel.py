import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.Qt.QtCore import QThreadPool
from pyqtgraph.exporters import ImageExporter

from .bifurcation_worker import BifurcationWorker


class BifurcationPanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self.config = None
        self.current_values = None
        self._sweep_gen = 0

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
        row1.addWidget(self.var_combo)

        row1.addStretch()
        close_btn = QtWidgets.QPushButton("\u00d7")
        close_btn.setFixedWidth(24)
        close_btn.clicked.connect(self.close_requested.emit)
        row1.addWidget(close_btn)

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
        self.cancel_btn.clicked.connect(self._cancel_sweep)
        row3.addWidget(self.cancel_btn)

        self.export_btn = QtWidgets.QPushButton("Export PNG...")
        self.export_btn.clicked.connect(self._export_plot)
        row3.addWidget(self.export_btn)
        layout.addLayout(row3)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.plot_widget = pg.PlotWidget()
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
        layout.addWidget(self.plot_widget)

    def _update_defaults(self):
        if self.config is None:
            return
        p = next(
            p for p in self.config.params if p.name == self.param_combo.currentText()
        )
        span = p.max_val - p.min_val
        self.min_spin.setValue(p.min_val + 0.01 * span)
        self.max_spin.setValue(p.max_val - 0.01 * span)
        self.plot_widget.setLabel("left", self.var_combo.currentText())

    def set_config(self, config, current_values):
        self._cancel_sweep()
        self._sweep_gen += 1
        self.config = config
        self.current_values = current_values
        self.param_combo.blockSignals(True)
        self.param_combo.clear()
        self.param_combo.addItems([p.name for p in config.params])
        self.param_combo.blockSignals(False)
        self.plot_data.setData([], [])
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
        base_params = {
            k: v for k, v in self.current_values.items() if k != param_name
        }

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._sweep_gen += 1
        gen = self._sweep_gen

        t_max = self.config.time_defaults["t_max"] * 4
        n = self.config.time_defaults["n"]

        worker = BifurcationWorker(
            self.config,
            base_params,
            param_name,
            param_values,
            n,
            transient,
            axis,
            t_max,
        )
        worker.signals.chunk_ready.connect(
            lambda vals, peaks, g=gen: self._on_chunk_ready(vals, peaks, g)
        )
        worker.signals.finished.connect(
            lambda g=gen: self._on_worker_finished(g)
        )
        worker.signals.error.connect(
            lambda msg, g=gen: self._on_worker_error(msg, g)
        )
        worker.signals.progress.connect(self.progress.setValue)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _cancel_sweep(self):
        if self._worker:
            self._worker._cancel = True
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_chunk_ready(self, vals, peaks_list, gen):
        if gen != self._sweep_gen:
            return
        lens = [len(p) for p in peaks_list]
        self.plot_data.setData(np.repeat(vals, lens), np.concatenate(peaks_list))

    def _on_worker_finished(self, gen):
        if gen != self._sweep_gen:
            return
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)

    def _on_worker_error(self, msg, gen):
        if gen != self._sweep_gen:
            return
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)

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
