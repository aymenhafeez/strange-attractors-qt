import numpy as np
from pyqtgraph.Qt.QtCore import QRunnable, pyqtSignal, QObject

from .solver import solve_rk4


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
        all_vals = []
        all_peaks = []
        n_params = len(self.param_values)
        turnround_ic = None

        for sweep_idx, param_seq in enumerate(
            [
                self.param_values,
                self.param_values[::-1],
            ]
        ):
            ic = turnround_ic
            cancelled = False
            for i, val in enumerate(param_seq):
                if self._cancel:
                    cancelled = True
                    break

                if i % max(1, n_params // 20) == 0:
                    progress = (sweep_idx * n_params + i) / (2 * n_params) * 100
                    self.signals.progress.emit(int(progress))

                try:
                    param_dict = {**self.base_params, self.sweep_param: float(val)}
                    pvals = np.ascontiguousarray(
                        [param_dict[p.name] for p in self.config.params],
                        dtype=np.float64,
                    )
                    y0 = (
                        ic
                        if ic is not None
                        else np.array(self.config.initial_conditions, dtype=np.float64)
                    )
                    # see integrator profiling notebook
                    n_eff = max(self.n_total // 10, 5000)
                    sol = solve_rk4(
                        self.config.equation,
                        y0,
                        0,
                        self.t_max,
                        n_eff,
                        pvals,
                    )
                    ic = sol[-1]

                    start = int(len(sol) * self.transient_frac)
                    data = sol[start:]
                    z = data[:, 2]
                    z_mid = (z.max() + z.min()) / 2
                    crossings = np.where((z[:-1] < z_mid) & (z[1:] >= z_mid))[0]

                    all_vals.append(val)

                    if len(crossings) == 0:
                        all_peaks.append(np.array([]))
                    else:
                        frac = (z_mid - z[crossings]) / (
                            z[crossings + 1] - z[crossings]
                        )
                        peaks = data[crossings, self.axis] + frac * (
                            data[crossings + 1, self.axis] - data[crossings, self.axis]
                        )
                        all_peaks.append(peaks)

                except Exception as e:
                    self.signals.error.emit(f"Failed at {self.sweep_param}={val}: {e}")
                    cancelled = True
                    break

            if cancelled:
                break
            if sweep_idx == 0:
                turnround_ic = ic

        self.signals.chunk_ready.emit(np.array(all_vals), all_peaks)
        self.signals.finished.emit()
