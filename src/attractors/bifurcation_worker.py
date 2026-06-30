import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from .solver import solve_attractor


class _BifurcationSignals(QObject):
    chunk_ready = pyqtSignal(object, object)
    finished = pyqtSignal()


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
    ):
        super().__init__()
        self.config = config
        self.base_params = base_params
        self.sweep_param = sweep_param
        self.param_values = param_values
        self.n_total = n_total
        self.transient_frac = transient_frac
        self.axis = axis
        self.signals = _BifurcationSignals()
        self._cancel = False

    def run(self):
        results_vals = []
        results_peaks = []

        for val in self.param_values:
            if self._cancel:
                break

            params = {**self.base_params, self.sweep_param: float(val)}
            sol = solve_attractor(self.config, params, self.n_total)

            start = int(len(sol) * self.transient_frac)
            data = sol[start:, self.axis]
            peaks = data[1:-1][(data[1:-1] > data[:-2]) & (data[1:-1] > data[2:])]

            results_vals.append(val)
            results_peaks.append(peaks)

        self.signals.chunk_ready.emit(np.array(results_vals), results_peaks)
        self.signals.finished.emit()
