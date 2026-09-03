import logging
import time

import numpy as np
from pyqtgraph.Qt.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.lyapunov import compute_lyapunov
from ..core.solver import solve_attractor
from ..perf import profiling_enabled

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("attractors.perf")


class SolveWorker(QObject):
    result_ready = pyqtSignal(int, object, bool)

    def __init__(self):
        super().__init__()
        self._cancel = False

    @pyqtSlot(int, object, dict, list, int, bool, float)
    def solve(self, request_id, config, values, ics, n, is_partial, t_max):
        self._cancel = False
        solutions = []
        profile = profiling_enabled()
        worker_start = time.perf_counter()

        try:
            for index, entry in enumerate(ics):
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

                kernel_start = time.perf_counter()
                sol = solve_attractor(
                    config,
                    values,
                    solve_n,
                    t_max=solve_t_max,
                    ic=ic,
                )
                kernel_ms = (time.perf_counter() - kernel_start) * 1000

                if profile:
                    perf_logger.info(
                        "solve.kernel completed in %.3f ms "
                        "(request_id=%s attractor=%s partial=%s trajectory=%s "
                        "n=%s t_max=%s points=%s)",
                        kernel_ms,
                        request_id,
                        config.name,
                        is_partial,
                        index,
                        solve_n,
                        solve_t_max,
                        len(sol),
                    )

                solutions.append(sol)

            worker_ms = (time.perf_counter() - worker_start) * 1000

            if profile:
                perf_logger.info(
                    "solve.worker completed in %.3f ms "
                    "(request_id=%s attractor=%s partial=%s trajectories=%s n=%s t_max=%s)",
                    worker_ms,
                    request_id,
                    config.name,
                    is_partial,
                    len(solutions),
                    n,
                    t_max,
                )

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
