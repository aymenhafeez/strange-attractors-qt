import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.bifurcation_worker import (
    BifurcationWorker,
    _axis_midplane_crossings,
    _sweep_sample_count,
)
from attractors.models import AttractorConfig, AttractorParam


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
        params=[AttractorParam("a", 1.0, 0.0, 10.0)],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )


def _config_with_t_min():
    return AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[AttractorParam("a", 1.0, 0.0, 10.0)],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 5, "t_max": 10, "n": 1000},
    )


def _crossing_solution(value):
    return np.array(
        [
            [value, 0.0, 0.0],
            [value + 1.0, 0.0, 1.0],
            [value + 2.0, 0.0, 0.0],
            [value + 3.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def test_worker_emits_cumulative_chunks_during_two_way_sweep(qapp, monkeypatch):
    def fake_solve_rk4(equation, y0, t_min, t_max, n, params):
        return _crossing_solution(params[0])

    monkeypatch.setattr("attractors.bifurcation_worker.solve_rk4", fake_solve_rk4)

    worker = BifurcationWorker(
        _config(),
        {},
        "a",
        np.linspace(0.0, 9.0, 10),
        1000,
        0.0,
        0,
        10.0,
    )
    chunks = []
    finished = []
    worker.signals.chunk_ready.connect(lambda vals, peaks: chunks.append((vals, peaks)))
    worker.signals.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(chunks) > 1
    assert finished == [True]
    assert len(chunks[-1][0]) == 20
    np.testing.assert_allclose(chunks[-1][0][:10], np.linspace(0.0, 9.0, 10))
    np.testing.assert_allclose(chunks[-1][0][10:], np.linspace(9.0, 0.0, 10))


def test_worker_does_not_emit_final_chunk_after_cancel(qapp, monkeypatch):
    worker = BifurcationWorker(
        _config(),
        {},
        "a",
        np.linspace(0.0, 9.0, 10),
        1000,
        0.0,
        0,
        10.0,
    )
    calls = 0

    def fake_solve_rk4(equation, y0, t_min, t_max, n, params):
        nonlocal calls
        calls += 1
        if calls == 2:
            worker.cancel()
        return _crossing_solution(params[0])

    monkeypatch.setattr("attractors.bifurcation_worker.solve_rk4", fake_solve_rk4)

    chunks = []
    finished = []
    worker.signals.chunk_ready.connect(lambda vals, peaks: chunks.append((vals, peaks)))
    worker.signals.finished.connect(lambda: finished.append(True))

    worker.run()

    assert finished == [True]
    assert chunks
    assert len(chunks[-1][0]) < 20


def test_worker_emits_finished_without_chunks_for_empty_sweep(qapp):
    worker = BifurcationWorker(
        _config(),
        {},
        "a",
        np.array([], dtype=np.float64),
        1000,
        0.0,
        0,
        10.0,
    )
    chunks = []
    finished = []
    worker.signals.chunk_ready.connect(lambda vals, peaks: chunks.append((vals, peaks)))
    worker.signals.finished.connect(lambda: finished.append(True))

    worker.run()

    assert chunks == []
    assert finished == [True]


def test_worker_passes_configured_t_min_to_solver(qapp, monkeypatch):
    calls = []

    def fake_solve_rk4(equation, y0, t_min, t_max, n, params):
        calls.append((t_min, t_max, n))
        return _crossing_solution(params[0])

    monkeypatch.setattr("attractors.bifurcation_worker.solve_rk4", fake_solve_rk4)

    worker = BifurcationWorker(
        _config_with_t_min(),
        {},
        "a",
        np.array([1.0], dtype=np.float64),
        1000,
        0.0,
        0,
        40.0,
        5.0,
    )

    worker.run()

    assert calls == [
        (5.0, 40.0, _sweep_sample_count(1000)),
        (5.0, 40.0, _sweep_sample_count(1000)),
    ]


def test_axis_midplane_crossings_interpolates_selected_axis():
    solution = np.array(
        [
            [0.0, 10.0, 0.0],
            [2.0, 20.0, 2.0],
            [4.0, 30.0, 0.0],
            [6.0, 40.0, 2.0],
        ],
        dtype=np.float64,
    )

    crossings = _axis_midplane_crossings(solution, axis=1)

    np.testing.assert_allclose(crossings, [15.0, 35.0])


def test_worker_emits_peak_snapshots_not_mutable_working_lists(qapp, monkeypatch):
    def fake_solve_rk4(equation, y0, t_min, t_max, n, params):
        return _crossing_solution(params[0])

    monkeypatch.setattr("attractors.bifurcation_worker.solve_rk4", fake_solve_rk4)

    worker = BifurcationWorker(
        _config(),
        {},
        "a",
        np.linspace(0.0, 2.0, 3),
        1000,
        0.0,
        0,
        10.0,
    )
    chunks = []
    worker.signals.chunk_ready.connect(lambda vals, peaks: chunks.append((vals, peaks)))

    worker.run()

    first_vals, first_peaks = chunks[0]
    assert len(first_vals) == 1
    assert len(first_peaks) == 1
    assert isinstance(first_peaks, tuple)


def test_worker_continues_from_previous_parameter_state_and_turns_round(
    qapp,
    monkeypatch,
):
    starts = []

    def fake_solve_rk4(equation, y0, t_min, t_max, n, params):
        starts.append(y0.copy())
        return _crossing_solution(params[0])

    monkeypatch.setattr("attractors.bifurcation_worker.solve_rk4", fake_solve_rk4)

    worker = BifurcationWorker(
        _config(),
        {},
        "a",
        np.array([2.0, 3.0], dtype=np.float64),
        1000,
        0.0,
        0,
        10.0,
    )

    worker.run()

    np.testing.assert_allclose(starts[0], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(starts[1], _crossing_solution(2.0)[-1])
    np.testing.assert_allclose(starts[2], _crossing_solution(3.0)[-1])
    np.testing.assert_allclose(starts[3], _crossing_solution(3.0)[-1])


def test_sweep_sample_count_matches_original_worker_density():
    assert _sweep_sample_count(1000) == 5000
    assert _sweep_sample_count(100000) == 10000
