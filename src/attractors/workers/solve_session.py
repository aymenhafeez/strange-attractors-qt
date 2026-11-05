# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import time
from dataclasses import dataclass, replace

from pyqtgraph.Qt import QtCore

from ..core.models import AttractorConfig
from ..core.solution_validation import validate_solutions
from ..perf import PerfProfiler

PARTIAL_N = 75000


def _initial_state():
    return {
        "solving": False,
        "valid": False,
        "stale": False,
        "partial": False,
        "last_error": None,
        "request_id": None,
        "attractor": None,
        "parameters": {},
        "n": None,
        "t_max": None,
        "trajectories": 0,
        "solution_points": [],
    }


def _partial_t_max(full_n, partial_n, full_t_max, t_min):
    if partial_n >= full_n:
        return full_t_max

    dt = (full_t_max - t_min) / full_n

    return t_min + partial_n * dt


@dataclass(frozen=True, eq=False)
class SolveRun:
    request_id: int | None
    config: AttractorConfig
    parameters: dict
    trajectory_specs: tuple  # ({"ic", "n", "t_max"}, ...)
    labels: tuple
    colours: tuple
    partial: bool
    analysis_ready: bool
    solutions: tuple = ()

    @property
    def attractor(self):
        return self.config.name

    @property
    def variables(self):
        return self.config.variables

    @property
    def t_min(self):
        return self.config.time_defaults.t_min

    @property
    def n(self):
        return max(spec["n"] for spec in self.trajectory_specs)

    @property
    def t_max(self):
        return max(spec["t_max"] for spec in self.trajectory_specs)

    @property
    def initial_conditions(self):
        return [spec["ic"] for spec in self.trajectory_specs]


def read_only(solutions):
    for solution in solutions:
        solution.setflags(write=False)

    return tuple(solutions)


class SolveSession(QtCore.QObject):
    state_changed = QtCore.pyqtSignal(dict)
    run_accepted = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str, bool)

    def __init__(self, solver, parent=None):
        super().__init__(parent)
        self._solver = solver
        self._perf = PerfProfiler()
        self._perf_token = None
        self._pending = None
        self._queued = None
        self.run = None
        self.analysis_run = None
        self.state = _initial_state()
        solver.solutions_ready.connect(self._on_result)

    def solve(self, full, config, values, n, t_max, trajectories, record):
        settings = (config, values, n, t_max, trajectories, record)
        # only keep the latest preview until the new one is ready
        if not full and self._pending is not None and self._pending.partial:
            self._queued = settings
            return

        self._solver.cancel_solve()
        self._dispatch(full, *settings)

    def mark_unsolved(self):
        self._solver.cancel_solve()
        self._pending = None
        self._queued = None
        self._set_state(
            solving=False,
            valid=False,
            stale=self.analysis_run is not None,
            partial=False,
            last_error=None,
        )

    def clear(self):
        self._solver.cancel_solve()
        self._pending = None
        self._queued = None
        self.run = None
        self.analysis_run = None
        self.state = _initial_state()
        self.state_changed.emit(self.state)

    def _set_state(self, **updates):
        self.state = {**self.state, **updates}
        self.state_changed.emit(self.state)

    def _dispatch(self, full, config, values, n, t_max, trajectories, record):
        self._queued = None
        if config is None:
            self._pending = None
            self.state = _initial_state()
            self._set_state(last_error="No attractor selected")
            return

        record = full or record
        t_min = config.time_defaults.t_min
        specs = []
        for trajectory in trajectories or [{"ic": config.initial_conditions}]:
            full_n = int(trajectory.get("n", n))
            full_t_max = float(trajectory.get("t_max", t_max))
            solve_n = full_n if record else min(full_n, PARTIAL_N)
            specs.append(
                {
                    "ic": [float(coord) for coord in trajectory["ic"]],
                    "n": solve_n,
                    "t_max": full_t_max
                    if record
                    else _partial_t_max(full_n, solve_n, full_t_max, t_min),
                }
            )

        request_id = self._solver.next_solve_request_id()
        run = SolveRun(
            request_id=request_id,
            config=config,
            parameters={str(key): float(value) for key, value in values.items()},
            trajectory_specs=tuple(specs),
            labels=tuple(t["label"] for t in trajectories) or ("T0",),
            colours=tuple(t["colour"].name() for t in trajectories) or (None,),
            partial=not full,
            analysis_ready=record,
        )
        self._pending = run
        self._set_state(
            solving=True,
            valid=False,
            stale=self.run is not None,
            partial=run.partial,
            last_error=None,
            request_id=request_id,
            attractor=run.attractor,
            parameters=run.parameters,
            n=run.n,
            t_max=run.t_max,
            trajectories=len(specs),
            solution_points=[],
        )
        self._perf_token = self._perf.start(
            "solve.request",
            key=request_id,
            attractor=run.attractor,
            full=full,
            partial=run.partial,
            n=run.n,
            t_max=run.t_max,
            trajectories=len(specs),
        )
        self._solver.request_solve(
            request_id, config, values, specs, run.n, run.partial, run.t_max
        )

    def _dispatch_queued(self):
        if self._queued is not None:
            self._dispatch(False, *self._queued)

    def _on_result(self, request_id, solutions, is_partial):
        run = self._pending
        if run is None or request_id != run.request_id:
            return

        self._pending = None
        token, self._perf_token = self._perf_token, None

        validation_start = time.perf_counter()
        if solutions is None:
            valid, message = False, "Solve failed"
        else:
            valid, message = validate_solutions(
                solutions, dimension=run.config.dimension
            )
        validation_ms = (time.perf_counter() - validation_start) * 1000

        if not valid:
            status = "failed" if solutions is None else "invalid"
            self._perf.finish(token, status=status, partial=is_partial)
            self._set_state(
                solving=False,
                valid=False,
                stale=self.run is not None,
                partial=False,
                last_error=message,
                solution_points=[],
            )
            self.failed.emit(message, is_partial)
            self._dispatch_queued()
            return

        self._perf.finish(token, status="ok", partial=is_partial)
        ui_start = time.perf_counter()

        accepted = replace(run, solutions=read_only(solutions))
        self.run = accepted
        if accepted.analysis_ready:
            self.analysis_run = accepted
        self.run_accepted.emit(accepted)
        self._set_state(
            solving=False,
            valid=not is_partial,
            stale=is_partial or self._queued is not None,
            partial=is_partial,
            last_error=None,
            solution_points=[len(solution) for solution in solutions],
        )

        if self._perf.enabled:
            self._perf._logger.info(
                "solve.ui completed in %.3f ms (request_id=%s partial=%s validation_ms=%.3f)",
                (time.perf_counter() - ui_start) * 1000,
                request_id,
                is_partial,
                validation_ms,
            )

        self._dispatch_queued()
