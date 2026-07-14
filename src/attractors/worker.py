from pyqtgraph.Qt.QtCore import QObject, pyqtSignal, pyqtSlot

from .lyapunov import compute_lyapunov
from .solver import solve_attractor


class SolveWorker(QObject):
    result_ready = pyqtSignal(object, bool)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(object, dict, list, int, bool, float)
    def solve(self, config, values, ics, n, is_partial, t_max):
        self._cancel = False
        solutions = []
        try:
            for ic in ics:
                if self._cancel:
                    return
                sol = solve_attractor(config, values, n, t_max=t_max, ic=ic)
                solutions.append(sol)
            if not self._cancel:
                self.result_ready.emit(solutions, is_partial)
        except Exception:
            if not self._cancel:
                self.result_ready.emit(None, False)


class LyapunovWorker(QObject):
    lyapunov_ready = pyqtSignal(object, float, object, object)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(object, dict)
    def compute(self, config, values):
        self._cancel = False

        try:
            pvals = [values[p.name] for p in config.params]
            lyap, ky_dim, t_hist, lyap_hist = compute_lyapunov(
                config.equation,
                config.initial_conditions,
                pvals,
                config.time_defaults["t_min"],
                config.time_defaults["t_max"],
                config.time_defaults["n"],
                return_history=True,
            )

            if not self._cancel:
                self.lyapunov_ready.emit(lyap, ky_dim, t_hist, lyap_hist)
        except Exception:
            pass
