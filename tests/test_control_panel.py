import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.control_panel import _slider_index, _slider_value


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
