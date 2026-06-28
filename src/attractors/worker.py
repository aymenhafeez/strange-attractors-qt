from PyQt6.QtCore import QObject, pyqtSignal
from .solver import solve_attractor


class SolveWorker(QObject):
    result_ready = pyqtSignal(object, bool)

    def __init__(self):
        super().__init__()
        self._cancel = False

    def solve(self, config, values, n):
        self._cancel = False

        try:
            sol = solve_attractor(config, values, n)
            if not self._cancel:
                self.result_ready.emit(sol, n is not None)
        except Exception:
            if not self._cancel:
                self.result_ready.emit(None, False)
