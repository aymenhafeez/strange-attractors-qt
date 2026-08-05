import logging

import numpy as np
from pyqtgraph.Qt.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.lyapunov import compute_lyapunov
from ..core.solver import solve_attractor

logger = logging.getLogger(__name__)


class SolveWorker(QObject):
    result_ready = pyqtSignal(int, object, bool)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(int, object, dict, list, int, bool, float)
    def solve(self, request_id, config, values, ics, n, is_partial, t_max):
        self._cancel = False
        solutions = []
        try:
            for entry in ics:
                if self._cancel:
                    return
                if isinstance(entry, dict):
                    ic = entry.get("ic")
                    solve_n = int(entry.get("n", n))
                    solve_t_max = float(entry.get("t_max", t_max))
                else:
                    ic = entry
                    solve_n = n
                    solve_t_max = t_max
                sol = solve_attractor(
                    config,
                    values,
                    solve_n,
                    t_max=solve_t_max,
                    ic=ic,
                )
                solutions.append(sol)
            if not self._cancel:
                self.result_ready.emit(request_id, solutions, is_partial)
        except Exception:
            logger.exception("Attractor solve failed")
            if not self._cancel:
                self.result_ready.emit(request_id, None, False)


class LyapunovWorker(QObject):
    lyapunov_ready = pyqtSignal(int, object, float, object, object)
    lyapunov_failed = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(int, object, dict, int, float)
    def compute(self, request_id, config, values, n=None, t_max=None):
        self._cancel = False

        try:
            solve_n = int(config.time_defaults.n if n is None else n)
            solve_t_max = float(config.time_defaults.t_max if t_max is None else t_max)
            pvals = np.ascontiguousarray(
                [values[p.name] for p in config.params], dtype=np.float64
            )
            initial_conditions = np.ascontiguousarray(
                config.initial_conditions, dtype=np.float64
            )
            lyap, ky_dim, t_hist, lyap_hist = compute_lyapunov(
                config.equation,
                initial_conditions,
                pvals,
                config.time_defaults.t_min,
                solve_t_max,
                solve_n,
            )

            if not self._cancel:
                self.lyapunov_ready.emit(request_id, lyap, ky_dim, t_hist, lyap_hist)
        except Exception as exc:
            logger.exception("Lyapunov computation failed")
            if not self._cancel:
                self.lyapunov_failed.emit(request_id, str(exc))
