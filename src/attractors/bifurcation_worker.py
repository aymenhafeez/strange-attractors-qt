import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from .solver import solve_attractor


class _BifurcationSignals(QObject):
    chunk_ready = pyqtSignal(object, object)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int)


class BifurcationWorker(QRunnable):
    def __init__(
        self,
        config,
        base_params,
        sweep_param,
        param_values,
        n_total,
        transient_frac,
        axis,
        t_max,
    ):
        super().__init__()
        self.config = config
        self.base_params = base_params
        self.sweep_param = sweep_param
        self.param_values = param_values
        self.n_total = n_total
        self.transient_frac = transient_frac
        self.axis = axis
        self.t_max = t_max
        self.signals = _BifurcationSignals()
        self._cancel = False

    def run(self):
        results_vals = []
        results_peaks = []
        n_params = len(self.param_values)

        for i, val in enumerate(self.param_values):
            if self._cancel:
                break

            if i % max(1, n_params // 20) == 0:
                self.signals.progress.emit(int(i / n_params * 100))

            try:
                params = {**self.base_params, self.sweep_param: float(val)}
                sol = solve_attractor(
                    self.config, params, self.n_total, t_max=self.t_max
                )

                start = int(len(sol) * self.transient_frac)
                data = sol[start:]
                z = data[:, 2]
                z_mid = (z.max() + z.min()) / 2

                crossings = np.where((z[:-1] < z_mid) & (z[1:] >= z_mid))[0]

                results_vals.append(val)
            except Exception as e:
                self.signals.error.emit(f"Failed at {self.sweep_param}={val}: {e}")
                break

            if len(crossings) == 0:
                results_peaks.append(np.array([]))
            else:
                frac = (z_mid - z[crossings]) / (z[crossings + 1] - z[crossings])
                peaks = data[crossings, self.axis] + frac * (
                    data[crossings + 1, self.axis] - data[crossings, self.axis]
                )
                results_peaks.append(peaks)

        self.signals.chunk_ready.emit(np.array(results_vals), results_peaks)
        self.signals.finished.emit()
