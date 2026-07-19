import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.Qt.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject

from .solver import solve_attractor


_PLANE_COLS = {"x": 0, "y": 1, "z": 2}
_AXIS_DATA = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}
_AXIS_LABELS = {"x": ("Y", "Z"), "y": ("X", "Z"), "z": ("X", "Y")}
DIR_MAP = {"both": "both", "rising": "positive", "falling": "negative"}
N_BINS = 96


def compute_poincare_crossings(sol, plane_axis, plane_value, direction="both"):
    plane_col = _PLANE_COLS[plane_axis]
    col_h, col_v = _AXIS_DATA[plane_axis]

    pv = sol[:, plane_col]

    up = np.where((pv[:-1] < plane_value) & (pv[1:] >= plane_value))[0]
    down = np.where((pv[:-1] >= plane_value) & (pv[1:] < plane_value))[0]

    if direction == "positive":
        idx = up
    elif direction == "negative":
        idx = down
    else:
        idx = np.concatenate([up, down])

    if len(idx) == 0:
        return np.array([]), np.array([])

    idx.sort()
    frac = (plane_value - pv[idx]) / (pv[idx + 1] - pv[idx])
    h = sol[idx, col_h] + frac * (sol[idx + 1, col_h] - sol[idx, col_h])
    v = sol[idx, col_v] + frac * (sol[idx + 1, col_v] - sol[idx, col_v])

    return h, v


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


class PoincarePanel(QtWidgets.QWidget):
    plane_changed = QtCore.pyqtSignal(str, float)
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._solutions = None
        self._config = None
        self._values = None
        self._worker = None
        self._solve_gen = 0

        self.setMinimumHeight(120)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        param_row = QtWidgets.QHBoxLayout()
        param_row.setSpacing(6)

        param_row.addWidget(QtWidgets.QLabel("t_max:"))
        self.tmax_spin = QtWidgets.QDoubleSpinBox()
        self.tmax_spin.setRange(1, 100000)
        self.tmax_spin.setSingleStep(100)
        self.tmax_spin.setDecimals(0)
        self.tmax_spin.setValue(500)
        param_row.addWidget(self.tmax_spin)

        param_row.addWidget(QtWidgets.QLabel("n:"))
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1000, 10000000)
        self.n_spin.setSingleStep(1000)
        self.n_spin.setValue(50000)
        param_row.addWidget(self.n_spin)

        self.solve_btn = QtWidgets.QPushButton("Run")
        self.solve_btn.clicked.connect(self._start_solve)
        param_row.addWidget(self.solve_btn)

        self.auto_check = QtWidgets.QCheckBox("Auto")
        self.auto_check.setChecked(True)
        self.auto_check.setToolTip("Auto solve when attractor parameters change")
        param_row.addWidget(self.auto_check)

        close_btn = QtWidgets.QPushButton("×")
        close_btn.setFixedWidth(24)
        close_btn.clicked.connect(self.close_requested.emit)
        param_row.addWidget(close_btn)

        layout.addLayout(param_row)

        ctrl_row = QtWidgets.QHBoxLayout()
        ctrl_row.setSpacing(6)

        ctrl_row.addWidget(QtWidgets.QLabel("Plane:"))
        self.plane_combo = QtWidgets.QComboBox()
        self.plane_combo.addItems(["x", "y", "z"])
        ctrl_row.addWidget(self.plane_combo)

        ctrl_row.addWidget(QtWidgets.QLabel("Value:"))
        self.value_spin = QtWidgets.QDoubleSpinBox()
        self.value_spin.setRange(-1e6, 1e6)
        self.value_spin.setSingleStep(0.5)
        self.value_spin.setDecimals(3)
        ctrl_row.addWidget(self.value_spin)

        ctrl_row.addWidget(QtWidgets.QLabel("Dir:"))
        self.dir_combo = QtWidgets.QComboBox()
        self.dir_combo.addItems(["both", "rising", "falling"])
        ctrl_row.addWidget(self.dir_combo)

        self.heatmap_check = QtWidgets.QCheckBox("Heatmap")
        self.heatmap_check.setChecked(False)
        ctrl_row.addWidget(self.heatmap_check)

        layout.addLayout(ctrl_row)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("k")
        self.plot_widget.setAspectLocked(True)
        layout.addWidget(self.plot_widget)

        self._scatter = self.plot_widget.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=1,
            symbolBrush=(255, 255, 255),
        )

        self._img = pg.ImageItem()
        cmap = pg.colormap.get("CMRmap", source="matplotlib")
        self._img.setLookupTable(cmap.getLookupTable())
        self._img.setVisible(False)
        self.plot_widget.addItem(self._img)

        self.plane_combo.currentTextChanged.connect(self._on_plane_changed)
        self.value_spin.editingFinished.connect(self._on_value_changed)
        self.dir_combo.currentTextChanged.connect(self._recompute)
        self.heatmap_check.toggled.connect(self._on_mode_changed)

        self._on_plane_changed(self.plane_combo.currentText())

    def set_attractor(self, config, values):
        self._config = config
        self._values = values
        if self.auto_check.isChecked():
            self._start_solve()

    def _set_solve_enabled(self, enabled):
        self.solve_btn.setEnabled(enabled)
        self.tmax_spin.setEnabled(enabled)
        self.n_spin.setEnabled(enabled)

    def _start_solve(self):
        if self._config is None:
            return
        self._cancel_solve()
        self._set_solve_enabled(False)
        self._solve_gen += 1
        gen = self._solve_gen

        t_max = self.tmax_spin.value()
        n = self.n_spin.value()
        worker = _PoincareWorker(self._config, self._values, n, t_max)
        worker.signals.result_ready.connect(
            lambda sol, g=gen: self._on_solve_result(sol, g)
        )
        worker.signals.finished.connect(lambda g=gen: self._on_solve_finished(g))
        worker.signals.error.connect(lambda msg, g=gen: self._on_solve_error(msg, g))
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _cancel_solve(self):
        if self._worker is not None:
            self._worker._cancel = True
            self._worker = None

    def _on_solve_result(self, sol, gen):
        if gen != self._solve_gen:
            return
        self._solutions = [sol]
        if sol is not None:
            plane = self.plane_combo.currentText()
            col = _PLANE_COLS[plane]
            midpoint = (sol[:, col].max() + sol[:, col].min()) / 2
            self.value_spin.blockSignals(True)
            self.value_spin.setValue(midpoint)
            self.value_spin.blockSignals(False)
            self._emit_plane()
        self._recompute()

    def _on_solve_finished(self, gen):
        if gen != self._solve_gen:
            return
        self._set_solve_enabled(True)
        self._worker = None

    def _on_solve_error(self, msg, gen):
        if gen != self._solve_gen:
            return
        self._set_solve_enabled(True)
        self._worker = None

    def _emit_plane(self):
        if not self.isVisible():
            return
        self.plane_changed.emit(self.plane_combo.currentText(), self.value_spin.value())

    def _on_plane_changed(self, plane):
        lh, lv = _AXIS_LABELS[plane]
        self.plot_widget.setLabel("bottom", lh)
        self.plot_widget.setLabel("left", lv)
        if self._solutions and len(self._solutions) > 0:
            col = _PLANE_COLS[plane]
            midpoint = (
                self._solutions[0][:, col].max() + self._solutions[0][:, col].min()
            ) / 2
            self.value_spin.blockSignals(True)
            self.value_spin.setValue(midpoint)
            self.value_spin.blockSignals(False)
        self._emit_plane()
        self._recompute()

    def _on_value_changed(self):
        self._emit_plane()
        self._recompute()

    def _on_mode_changed(self):
        heatmap = self.heatmap_check.isChecked()
        self._scatter.setVisible(not heatmap)
        self._img.setVisible(heatmap)
        self._recompute()

    def recompute(self):
        self._recompute()

    def _recompute(self):
        if self._solutions is None:
            return

        plane = self.plane_combo.currentText()
        value = self.value_spin.value()
        direction = DIR_MAP[self.dir_combo.currentText()]

        all_h = []
        all_v = []

        for sol in self._solutions:
            h, v = compute_poincare_crossings(sol, plane, value, direction)
            all_h.append(h)
            all_v.append(v)

        if self.heatmap_check.isChecked():
            self._scatter.setData([], [])
            if all_h:
                combined = np.concatenate(all_h)
                if len(combined) > 0:
                    h_all = combined
                    v_all = np.concatenate(all_v)
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
                    self.plot_widget.autoRange()
                    return
            self._img.setVisible(False)
        else:
            self._img.setVisible(False)
            if all_h:
                combined = np.concatenate(all_h)
                if len(combined) > 0:
                    self._scatter.setData(combined, np.concatenate(all_v))
                    self.plot_widget.autoRange()
                    return
            self._scatter.setData([], [])
