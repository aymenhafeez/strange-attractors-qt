import numpy as np
import pytest
from pyqtgraph.Qt import QtCore, QtWidgets

from attractors.control_panel import ControlPanel
from attractors.data_view_panel import DataViewPanel, TrajectoryTableModel
from attractors.models import AttractorConfig, AttractorParam


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _display(model, row, column):
    index = model.index(row, column)
    return model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)


def test_trajectory_table_model_shows_sampled_rows_with_time(qapp):
    model = TrajectoryTableModel()
    model.set_sample_size(3)
    model.set_solutions(
        [np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]])],
        t_min=2,
        t_max=10,
    )

    assert model.rowCount() == 3
    assert model.columnCount() == 6
    assert _display(model, 0, 0) == "0"
    assert _display(model, 0, 1) == "0"
    assert _display(model, 0, 2) == "4"
    assert _display(model, 1, 1) == "1"
    assert _display(model, 1, 3) == "4"
    assert _display(model, 2, 1) == "3"
    assert _display(model, 2, 5) == "12"


def test_trajectory_table_model_can_show_full_rows(qapp):
    model = TrajectoryTableModel()
    model.set_sample_size(1)
    model.set_solutions(
        [
            np.array([[1, 2, 3], [4, 5, 6]]),
            np.array([[7, 8, 9]]),
        ],
        t_min=0,
        trajectory_specs=[{"t_max": 4}, {"t_max": 10}],
    )

    model.set_sampled(False)

    assert model.rowCount() == 3
    assert _display(model, 1, 0) == "0"
    assert _display(model, 1, 1) == "1"
    assert _display(model, 1, 2) == "4"
    assert _display(model, 2, 0) == "1"
    assert _display(model, 2, 1) == "0"
    assert _display(model, 2, 2) == "10"


def test_data_view_panel_summarises_visible_and_total_rows(qapp):
    panel = DataViewPanel()
    panel.sample_size.setValue(10)

    panel.set_solutions(
        [np.zeros((15, 3)), np.zeros((1, 3))],
        t_min=0,
        t_max=1,
        partial=True,
    )

    assert panel.model.rowCount() == 11
    assert panel.summary_label.text() == "11 / 16 partial"


def test_data_view_panel_keeps_partial_summary_when_sampling_changes(qapp):
    panel = DataViewPanel()
    panel.sample_size.setValue(10)

    panel.set_solutions(
        [np.zeros((15, 3))],
        t_min=0,
        t_max=1,
        partial=True,
    )

    panel.sample_mode.setChecked(False)
    assert panel.summary_label.text() == "15 / 15 partial"

    panel.sample_mode.setChecked(True)
    assert panel.summary_label.text() == "10 / 15 partial"


def test_data_view_panel_populates_context_tabs(qapp):
    config = AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[AttractorParam("a", 1.5, 0.0, 3.0, 0.5)],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )
    panel = DataViewPanel()

    panel.set_solutions(
        [
            np.array([[1.0, 2.0, 3.0], [4.0, 7.0, 9.0]]),
            np.array([[0.0, -1.0, 5.0]]),
        ],
        t_min=0,
        t_max=10,
        trajectory_specs=[
            {"ic": [1.0, 2.0, 3.0], "t_max": 10},
            {"ic": [0.0, -1.0, 5.0], "t_max": 4},
        ],
        config=config,
        values={"a": 2.0},
    )

    assert panel.tabs.tabText(0) == "Samples"
    assert panel.tabs.tabText(1) == "Trajectories"
    assert panel.tabs.tabText(2) == "Parameters"
    assert panel.tabs.tabText(3) == "Bounds"
    assert panel.tabs.tabText(4) == "Measures"
    assert panel.trajectory_model.rowCount() == 2
    assert _display(panel.trajectory_model, 0, 1) == "2"
    assert _display(panel.trajectory_model, 0, 5) == "4"
    assert panel.parameter_model.rowCount() == 1
    assert _display(panel.parameter_model, 0, 0) == "a"
    assert _display(panel.parameter_model, 0, 1) == "2"
    assert panel.bounds_model.rowCount() == 3
    assert _display(panel.bounds_model, 0, 0) == "x"
    assert _display(panel.bounds_model, 0, 1) == "0"
    assert _display(panel.bounds_model, 0, 2) == "4"
    assert panel.measures_model.rowCount() == panel.model.rowCount()


def test_control_panel_places_data_view_below_controls(qapp):
    config = AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )
    panel = ControlPanel()

    panel.configure(config)

    assert isinstance(panel.data_view, DataViewPanel)
    assert panel.panel_layout.indexOf(panel.content_frame) == 0
    assert panel.content_splitter.indexOf(panel.controls_scroll) == 0
    assert panel.content_splitter.indexOf(panel.data_view) == 1
