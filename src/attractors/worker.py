from PyQt6.QtCore import QObject, pyqtSignal
from .solver import solve_attractor


class SolveWorker(QObject):
    result_ready = pyqtSignal(object, bool)
    lyapunov_ready = pyqtSignal(object, float)

    def __init__(self):
        super().__init__()
        self._cancel = False

    def solve(self, config, values, n):
        self._cancel = False

        try:
            sol = solve_attractor(config, values, n or config.time_defaults["n"])
            if not self._cancel:
                self.result_ready.emit(sol, n is not None)

            from .lyapunov import compute_lyapunov

            pvals = [values[p.name] for p in config.params]
            lyap, ky_dim = compute_lyapunov(
                config.equation,
                config.initial_conditions,
                pvals,
                config.time_defaults["t_min"],
                config.time_defaults["t_max"],
                config.time_defaults["n"],
            )

            if not self._cancel:
                self.lyapunov_ready.emit(lyap, ky_dim)

        except Exception:
            if not self._cancel:
                self.result_ready.emit(None, False)
