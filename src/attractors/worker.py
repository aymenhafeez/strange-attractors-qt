from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .lyapunov import compute_lyapunov
from .solver import solve_attractor


class SolveWorker(QObject):
    result_ready = pyqtSignal(object, bool)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(object, dict, object)
    def solve(self, config, values, n):
        self._cancel = False

        try:
            sol = solve_attractor(config, values, n or config.time_defaults["n"])
            if not self._cancel:
                self.result_ready.emit(sol, n is not None)
        except Exception:
            if not self._cancel:
                self.result_ready.emit(None, False)


class LyapunovWorker(QObject):
    lyapunov_ready = pyqtSignal(object, float)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(object, dict)
    def compute(self, config, values):
        self._cancel = False

        if config.lyapunov_equation is None:
            return

        pvals = [values[p.name] for p in config.params]
        lyap, ky_dim = compute_lyapunov(
            config.lyapunov_equation,
            config.initial_conditions,
            pvals,
            config.time_defaults["t_min"],
            config.time_defaults["t_max"],
            config.time_defaults["n"],
        )

        if not self._cancel:
            self.lyapunov_ready.emit(lyap, ky_dim)
