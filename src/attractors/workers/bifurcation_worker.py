# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
from pyqtgraph.Qt.QtCore import QObject, QRunnable, pyqtSignal
from scipy.signal import find_peaks

from ..core.sections import COORDINATE_COLUMNS, plane_crossings
from ..core.solution_validation import validate_solutions
from ..core.solver import solve_rk4

SWEEP_DIRECTIONS = 2


class _BifurcationSignals(QObject):
    chunk_ready = pyqtSignal(object, object)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int)


def _sweep_sample_count(n_total):
    return max(n_total // 10, 5000)


def _axis_midplane_crossings(solution, axis):
    dimension = solution.shape[1]
    section_axis = 2 if dimension == 3 and axis != 2 else (axis + 1) % dimension
    series = solution[:, section_axis]
    level = (series.min() + series.max()) / 2

    crossings = plane_crossings(
        solution, COORDINATE_COLUMNS[section_axis], level, direction="positive"
    )

    return crossings.points[:, axis]


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
        t_min=0,
        *,
        sampling="Midplane crossings",
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
        self.t_min = t_min
        self.sampling = sampling
        self.signals = _BifurcationSignals()
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        all_vals = []
        all_peaks = []
        n_params = len(self.param_values)
        if n_params == 0:
            self.signals.finished.emit()
            return

        emit_interval = max(1, n_params // 20)
        last_emitted_count = 0
        turnround_ic = None
        cancelled = False

        for sweep_idx, param_seq in enumerate(
            [
                self.param_values,
                self.param_values[::-1],
            ]
        ):
            ic = turnround_ic
            for i, val in enumerate(param_seq):
                if self._cancel:
                    cancelled = True
                    break

                if i % emit_interval == 0:
                    progress = (
                        (sweep_idx * n_params + i) / (SWEEP_DIRECTIONS * n_params) * 100
                    )
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
                    solution = solve_rk4(
                        self.config.equation,
                        y0,
                        self.t_min,
                        self.t_max,
                        _sweep_sample_count(self.n_total),
                        pvals,
                    )
                    valid, message = validate_solutions(
                        [solution], dimension=self.config.dimension
                    )
                    if not valid:
                        raise ValueError(message)
                    ic = solution[-1]

                    start = int(len(solution) * self.transient_frac)
                    tail = solution[start:]
                    series = tail[:, self.axis]

                    if self.sampling == "Envolope":
                        peaks = np.unique([series.min(), series.max()])
                    elif self.sampling == "Local maxima":
                        indices, _ = find_peaks(series)
                        peaks = series[indices]
                    elif self.sampling == "Midplane crossings":
                        peaks = _axis_midplane_crossings(tail, self.axis)

                    all_vals.append(val)
                    all_peaks.append(peaks)

                    if len(all_vals) - last_emitted_count >= emit_interval:
                        self.signals.chunk_ready.emit(
                            np.array(all_vals, dtype=np.float64),
                            tuple(peak.copy() for peak in all_peaks),
                        )
                        last_emitted_count = len(all_vals)

                except Exception as exc:  # noqa: BLE001
                    self.signals.error.emit(
                        f"Failed at {self.sweep_param}={val}: {exc}"
                    )
                    cancelled = True
                    break

            if cancelled:
                break
            if sweep_idx == 0:
                turnround_ic = ic

        if not cancelled:
            self.signals.chunk_ready.emit(
                np.array(all_vals, dtype=np.float64),
                tuple(peak.copy() for peak in all_peaks),
            )
        self.signals.finished.emit()
