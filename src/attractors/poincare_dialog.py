import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
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

from .solver import solve_attractor


_PLANE_COLS = {"x": 0, "y": 1, "z": 2}
_AXIS_LABELS = {"x": ("Y", "Z"), "y": ("X", "Z"), "z": ("X", "Y")}
_AXIS_DATA = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}

N_BINS = 96


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
        except Exception as e:
            if not self._cancel:
                self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class PoincareSectionDialog(QDialog):
    def __init__(self, config, values, sol, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Poincaré Section")
        self.resize(600, 650)
        self._config = config
        self._values = values
        self._sol = sol
        self._worker = None

        layout = QVBoxLayout(self)

        solve_row = QHBoxLayout()
        solve_row.addWidget(QLabel("t_max:"))
        self.tmax_spin = QDoubleSpinBox()
        self.tmax_spin.setRange(1, 1e6)
        self.tmax_spin.setSingleStep(100)
        self.tmax_spin.setDecimals(0)
        self.tmax_spin.setValue(config.time_defaults["t_max"] * 10)
        solve_row.addWidget(self.tmax_spin)

        solve_row.addWidget(QLabel("n:"))
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1000, 10_000_000)
        self.n_spin.setSingleStep(100_000)
        self.n_spin.setValue(config.time_defaults["n"] * 10)
        solve_row.addWidget(self.n_spin)

        self.run_btn = QPushButton("▶ Run")
        self.run_btn.clicked.connect(self._run_solve)
        solve_row.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("■ Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_solve)
        solve_row.addWidget(self.cancel_btn)

        layout.addLayout(solve_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        section_row = QHBoxLayout()
        section_row.addWidget(QLabel("Plane:"))
        self.plane_combo = QComboBox()
        self.plane_combo.addItems(["x", "y", "z"])
        self.plane_combo.setCurrentText("z")
        section_row.addWidget(self.plane_combo)

        section_row.addWidget(QLabel("Value:"))
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(-1e6, 1e6)
        self.value_spin.setSingleStep(0.5)
        self.value_spin.setDecimals(3)
        section_row.addWidget(self.value_spin)

        self.heatmap_check = QCheckBox("Heatmap")
        self.heatmap_check.setChecked(False)
        section_row.addWidget(self.heatmap_check)

        self.export_btn = QPushButton("Export PNG...")
        self.export_btn.clicked.connect(self._export_plot)
        section_row.addWidget(self.export_btn)

        layout.addLayout(section_row)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("k")
        self.plot_widget.setAspectLocked(True)
        layout.addWidget(self.plot_widget)

        self._scatter = self.plot_widget.plot(
            [], [],
            pen=None,
            symbol="o",
            symbolSize=1,
            symbolBrush=(255, 255, 255),
        )

        self._img = pg.ImageItem()
        cmap = pg.colormap.get("CET-L1")
        self._img.setLookupTable(cmap.getLookupTable())
        self._img.setVisible(False)
        self.plot_widget.addItem(self._img)

        self.plane_combo.currentTextChanged.connect(self._on_plane_changed)
        self.value_spin.editingFinished.connect(self._recompute)
        self.heatmap_check.toggled.connect(self._on_mode_changed)

        self._on_plane_changed(self.plane_combo.currentText())

    def _run_solve(self):
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)

        worker = _PoincareWorker(
            self._config,
            self._values,
            self.n_spin.value(),
            self.tmax_spin.value(),
        )
        worker.signals.result_ready.connect(self._on_solve_result)
        worker.signals.finished.connect(self._on_solve_finished)
        worker.signals.error.connect(self._on_solve_error)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_solve_result(self, sol):
        self._sol = sol
        self._on_plane_changed(self.plane_combo.currentText())

    def _on_solve_finished(self):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)

    def _on_solve_error(self, msg):
        self.run_btn.setText(f"Error: {msg}")
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)

    def _cancel_solve(self):
        if self._worker:
            self._worker._cancel = True
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)

    def _on_plane_changed(self, plane):
        if self._sol is None:
            return
        col = _PLANE_COLS[plane]
        midpoint = (self._sol[:, col].max() + self._sol[:, col].min()) / 2
        self.value_spin.blockSignals(True)
        self.value_spin.setValue(midpoint)
        self.value_spin.blockSignals(False)

        lh, lv = _AXIS_LABELS[plane]
        self.plot_widget.setLabel("bottom", lh)
        self.plot_widget.setLabel("left", lv)

        self._recompute()

    def _on_mode_changed(self):
        heatmap = self.heatmap_check.isChecked()
        self._scatter.setVisible(not heatmap)
        self._img.setVisible(heatmap)
        self._recompute()

    def _recompute(self):
        if self._sol is None:
            return

        plane = self.plane_combo.currentText()
        value = self.value_spin.value()
        plane_col = _PLANE_COLS[plane]
        col_h, col_v = _AXIS_DATA[plane]

        pv = self._sol[:, plane_col]
        up = np.where((pv[:-1] < value) & (pv[1:] >= value))[0]
        down = np.where((pv[:-1] >= value) & (pv[1:] < value))[0]
        idx = np.concatenate([up, down])

        if len(idx) == 0:
            self._scatter.setData([], [])
            self._img.setVisible(False)
            return

        idx.sort()
        frac = (value - pv[idx]) / (pv[idx + 1] - pv[idx])
        h = self._sol[idx, col_h] + frac * (self._sol[idx + 1, col_h] - self._sol[idx, col_h])
        v = self._sol[idx, col_v] + frac * (self._sol[idx + 1, col_v] - self._sol[idx, col_v])

        if self.heatmap_check.isChecked():
            self._scatter.setData([], [])
            heatmap, xedges, yedges = np.histogram2d(h, v, bins=N_BINS)
            self._img.setImage(np.log1p(heatmap))
            self._img.setRect(pg.QtCore.QRectF(
                xedges[0], yedges[0],
                xedges[-1] - xedges[0],
                yedges[-1] - yedges[0],
            ))
            self._img.setVisible(True)
            self.plot_widget.autoRange()
        else:
            self._img.setVisible(False)
            self._scatter.setData(h, v)

    def _export_plot(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Poincaré section", "", "PNG (*.png)"
        )
        if path:
            exporter = ImageExporter(self.plot_widget.plotItem)
            exporter.export(path)
