import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from pyqtgraph.exporters import ImageExporter

from .bifurcation_worker import BifurcationWorker


class BifurcationDialog(QDialog):
    def __init__(self, config, current_values, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bifurcation Diagram")
        self.resize(800, 600)

        self.config = config
        self.current_values = current_values
        self._threadpool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Sweep param:"))
        self.param_combo = QComboBox()
        self.param_combo.addItems([p.name for p in config.params])
        self.param_combo.currentTextChanged.connect(self._update_defaults)
        row1.addWidget(self.param_combo)

        row1.addWidget(QLabel("  Variable:"))
        self.var_combo = QComboBox()
        self.var_combo.addItems(["x", "y", "z"])
        row1.addWidget(self.var_combo)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("From:"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1e6, 1e6)
        self.min_spin.setSingleStep(0.01)
        row2.addWidget(self.min_spin)

        row2.addWidget(QLabel("To:"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1e6, 1e6)
        self.max_spin.setSingleStep(0.01)
        row2.addWidget(self.max_spin)

        row2.addWidget(QLabel("Steps:"))
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(10, 10000)
        self.steps_spin.setValue(500)
        row2.addWidget(self.steps_spin)

        row2.addWidget(QLabel("Transient:"))
        self.transient_spin = QDoubleSpinBox()
        self.transient_spin.setRange(0.0, 0.99)
        self.transient_spin.setSingleStep(0.05)
        self.transient_spin.setValue(0.7)
        row2.addWidget(self.transient_spin)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.clicked.connect(self._run_sweep)
        row3.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("■ Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_sweep)
        row3.addWidget(self.cancel_btn)

        self.export_btn = QPushButton("Export PNG...")
        self.export_btn.clicked.connect(self._export_plot)
        row3.addWidget(self.export_btn)
        layout.addLayout(row3)

        self.progress = QProgressBar()
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
            symbolSize=1,
            symbolBrush=(255, 255, 255),
        )
        layout.addWidget(self.plot_widget)

        self._update_defaults()

    def _update_defaults(self):
        p = next(
            p for p in self.config.params if p.name == self.param_combo.currentText()
        )
        span = p.max_val - p.min_val
        self.min_spin.setValue(p.min_val + 0.01 * span)
        self.max_spin.setValue(p.max_val - 0.01 * span)
        self.plot_widget.setLabel("left", self.var_combo.currentText())

    def _run_sweep(self):
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
        worker.signals.chunk_ready.connect(self._on_chunk_ready)
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.progress.connect(self.progress.setValue)
        self._worker = worker
        self._threadpool.start(worker)

    def _on_chunk_ready(self, vals, peaks_list):
        lens = [len(p) for p in peaks_list]
        self.plot_data.setData(np.repeat(vals, lens), np.concatenate(peaks_list))

    def _on_worker_finished(self):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)

    def _cancel_sweep(self):
        if self._worker:
            self._worker._cancel = True
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_worker_error(self, msg):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)
        self.run_btn.setText(f"Error: {msg}")

    def _export_plot(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export bifurcation diagram",
            "",
            "PNG (*.png);;SVG (*.svg)",
        )
        if path:
            exporter = ImageExporter(self.plot_widget.plotItem)
            exporter.export(path)
