import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.control_panel import _slider_index, _slider_value, ControlPanel
from attractors.models import AttractorConfig, AttractorParam


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_slider_index_maps_default_to_expected_integer():
    assert _slider_index(10.0, 0.0, 0.5) == 20


def test_slider_value_maps_index_to_float_value():
    assert _slider_value(20, 0.0, 0.5) == pytest.approx(10.0)


def test_slider_index_and_value_round_trip_with_negative_min():
    value = -1.25
    min_val = -5.0
    step = 0.25

    index = _slider_index(value, min_val, step)

    assert _slider_value(index, min_val, step) == pytest.approx(value)


def test_slider_index_rounds_to_nearest_step():
    assert _slider_index(0.30000000000000004, 0.0, 0.1) == 3


def test_control_panel_gets_current_values_returns_config_defaults(qapp):
    config = AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[
            AttractorParam("a", 1.5, 0.0, 10.0, 0.5),
            AttractorParam("b", -2.0, -5.0, 5.0, 0.25),
        ],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )

    panel = ControlPanel()
    panel.configure(config)

    assert panel.get_current_values() == {
        "a": pytest.approx(1.5),
        "b": pytest.approx(-2.0),
    }


def test_control_panel_reset_to_defaults_restores_slider_values(qapp):
    config = AttractorConfig(
        name="test",
        equation=lambda state, t, params: state,
        params=[
            AttractorParam("a", 1.5, 0.0, 10.0, 0.5),
        ],
        initial_conditions=[0.0, 0.0, 0.0],
        time_defaults={"t_min": 0, "t_max": 10, "n": 1000},
    )

    panel = ControlPanel()
    panel.configure(config)

    param, slider, _, _ = panel.slider_rows[0]
    slider.setValue(_slider_index(4.0, param.min_val, param.step))

    assert panel.get_current_values()["a"] == pytest.approx(4.0)

    panel.reset_to_defaults()

    assert panel.get_current_values()["a"] == pytest.approx(1.5)
