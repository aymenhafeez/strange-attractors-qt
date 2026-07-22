from types import SimpleNamespace

import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.app import Window
from attractors.models import AttractorConfig, AttractorParam
from attractors.worker import LyapunovWorker, SolveWorker


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _config():
    return AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[AttractorParam("a", 1.0, 0.0, 2.0)],
        initial_conditions=[0.0, 1, 2.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )


def test_solve_worker_emits_one_solution_per_initial_condition(qapp, monkeypatch):
    def fake_solve_attractor(config, values, n, t_max=None, ic=None):
        return np.array([ic], dtype=np.float64)

    monkeypatch.setattr("attractors.worker.solve_attractor", fake_solve_attractor)

    worker = SolveWorker()
    emitted = []
    worker.result_ready.connect(
        lambda request_id, solutions, is_partial: emitted.append(
            (request_id, solutions, is_partial)
        )
    )

    worker.solve(
        7,
        _config(),
        {"a": 1.0},
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        123,
        True,
        50.0,
    )

    assert len(emitted) == 1

    request_id, solutions, is_partial = emitted[0]
    assert request_id == 7
    assert is_partial is True
    assert len(solutions) == 2
    np.testing.assert_allclose(solutions[0], [[1.0, 2.0, 3.0]])
    np.testing.assert_allclose(solutions[1], [[4.0, 5.0, 6.0]])


def test_solve_worker_emits_failure_result_on_exception(qapp, monkeypatch):
    def fake_solve_attractor(config, values, n, t_max=None, ic=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("attractors.worker.solve_attractor", fake_solve_attractor)

    worker = SolveWorker()
    emitted = []
    worker.result_ready.connect(
        lambda request_id, solutions, is_partial: emitted.append(
            (request_id, solutions, is_partial)
        )
    )

    worker.solve(
        8,
        _config(),
        {"a": 1.0},
        [[1.0, 2.0, 3.0]],
        123,
        True,
        50.0,
    )

    assert emitted == [(8, None, False)]


def test_solve_worker_cancel_suppresses_emit(qapp, monkeypatch):
    worker = SolveWorker()

    def fake_solve_attractor(config, values, n, t_max=None, ic=None):
        worker._cancel = True
        return np.array([ic], dtype=np.float64)

    monkeypatch.setattr("attractors.worker.solve_attractor", fake_solve_attractor)

    emitted = []
    worker.result_ready.connect(
        lambda request_id, solutions, is_partial: emitted.append(
            (request_id, solutions, is_partial)
        )
    )

    worker.solve(
        9,
        _config(),
        {"a": 1.0},
        [[1.0, 2.0, 3.0]],
        123,
        True,
        50.0,
    )

    assert emitted == []


def test_lyapunov_worker_emits_computation_result(qapp, monkeypatch):
    captured = {}

    def fake_compute_lyapunov(equation, initial_conditions, params, t_min, t_max, n):
        captured["initial_conditions"] = initial_conditions
        captured["params"] = params
        captured["time"] = (t_min, t_max, n)
        return (
            np.array([0.1, 0.0, -1.0]),
            2.1,
            np.array([1.0, 2.0]),
            np.array([[0.1, 0.0, -1.0], [0.1, 0.0, -1.0]]),
        )

    monkeypatch.setattr("attractors.worker.compute_lyapunov", fake_compute_lyapunov)

    worker = LyapunovWorker()
    emitted = []
    worker.lyapunov_ready.connect(
        lambda request_id, lyap, ky, t_hist, lyap_hist: emitted.append(
            (request_id, lyap, ky, t_hist, lyap_hist)
        )
    )

    worker.compute(11, _config(), {"a": 1.5})

    assert len(emitted) == 1

    request_id, lyap, ky, t_hist, lyap_hist = emitted[0]
    assert request_id == 11
    assert lyap == pytest.approx([0.1, 0.0, -1.0])
    assert ky == pytest.approx(2.1)
    assert t_hist == pytest.approx([1.0, 2.0])
    np.testing.assert_allclose(lyap_hist, [[0.1, 0.0, -1.0], [0.1, 0.0, -1.0]])

    assert captured["initial_conditions"].dtype == np.float64
    np.testing.assert_allclose(captured["initial_conditions"], [0.0, 1.0, 2.0])
    assert captured["params"].dtype == np.float64
    np.testing.assert_allclose(captured["params"], [1.5])
    assert captured["time"] == (0, 10, 1000)


def test_lyapunov_worker_suppresses_exception(qapp, monkeypatch):
    def fake_compute_lyapunov(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr("attractors.worker.compute_lyapunov", fake_compute_lyapunov)

    worker = LyapunovWorker()
    emitted = []
    worker.lyapunov_ready.connect(
        lambda request_id, lyap, ky, t_hist, lyap_hist: emitted.append(
            (request_id, lyap, ky, t_hist, lyap_hist)
        )
    )

    worker.compute(12, _config(), {"a": 1.5})

    assert emitted == []


def test_window_ignores_stale_solve_results():
    class Scene:
        def __init__(self):
            self.displayed = False

        def display_solutions(self, solutions, is_partial):
            self.displayed = True

    window = SimpleNamespace(_active_solve_request_id=2, scene=Scene())

    Window._on_solve_result(window, 1, [np.zeros((1, 3))], False)

    assert window.scene.displayed is False


def test_window_displays_stale_partial_solve_as_preview():
    class Scene:
        def __init__(self):
            self.displayed = False
            self.refreshed = False

        def display_solutions(self, solutions, is_partial):
            self.displayed = True
            self.is_partial = is_partial

        def refresh_colours(self):
            self.refreshed = True

    window = SimpleNamespace(_active_solve_request_id=2, scene=Scene())

    Window._on_solve_result(window, 1, [np.zeros((1, 3))], True)

    assert window.scene.displayed is True
    assert window.scene.is_partial is True
    assert window.scene.refreshed is True


def test_window_ignores_stale_lyapunov_results():
    class Scene:
        def __init__(self):
            self.lyapunov_set = False

        def set_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
            self.lyapunov_set = True

    window = SimpleNamespace(_active_lyapunov_request_id=2, scene=Scene())

    Window._on_lyapunov_result(
        window,
        1,
        np.array([0.1, 0.0, -1.0]),
        2.1,
        np.array([1.0]),
        np.array([[0.1, 0.0, -1.0]]),
    )

    assert window.scene.lyapunov_set is False
