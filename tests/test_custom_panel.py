import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.custom_panel import CustomPanel


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _set_equations(panel, equations):
    for text_edit, equation in zip(panel.text_edits, equations):
        text_edit.setPlainText(equation)


def test_compile_requires_all_three_equations(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("x", "y", ""))

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_compile()

    assert emitted == []
    assert not panel.status_label.isHidden()
    assert panel.status_label.text() == "All three equations are required."


def test_compile_shows_parse_error(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("a * (y - x", "x", "z"))

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_compile()

    assert emitted == []
    assert not panel.status_label.isHidden()
    assert panel.status_label.text().startswith("Syntax error:")


def test_compile_without_parameters_emits_config_immediately(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("y", "-x", "-z"))
    panel.ic_spins[0].setValue(1.0)
    panel.ic_spins[1].setValue(2.0)
    panel.ic_spins[2].setValue(3.0)

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_compile()

    assert len(emitted) == 1

    config = emitted[0]
    assert config.name == "Custom"
    assert config.params == []
    assert config.initial_conditions == [1.0, 2.0, 3.0]
    assert config.time_defaults == {"t_min": 0, "t_max": 50, "n": 100000}
    assert config.equation_text == "dx/dt = y\ndy/dt = -x\ndz/dt = -z"

    result = config.equation(
        np.array([1.0, 2.0, 3.0], dtype=np.float64),
        0.0,
        np.array([], dtype=np.float64),
    )

    assert result == pytest.approx([2.0, -1.0, -3.0])


def test_compile_with_parameters_builds_range_editors_before_emitting(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("a * x", "b * y", "z"))

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_compile()

    assert emitted == []
    assert not panel.range_group.isHidden()
    assert not panel.solve_btn.isHidden()
    assert panel.compile_btn.isHidden()
    assert set(panel._range_widgets) == {"a", "b"}


def test_solve_after_parameter_compile_emits_config_with_ranges(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("a * x", "b * y", "z"))
    panel._on_compile()

    panel._range_widgets["a"][0].setValue(-1.0)
    panel._range_widgets["a"][1].setValue(1.0)
    panel._range_widgets["a"][2].setValue(0.1)

    panel._range_widgets["b"][0].setValue(10.0)
    panel._range_widgets["b"][1].setValue(20.0)
    panel._range_widgets["b"][2].setValue(0.5)

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_solve()

    assert len(emitted) == 1

    config = emitted[0]
    params = {p.name: p for p in config.params}

    assert set(params) == {"a", "b"}

    assert params["a"].min_val == pytest.approx(-1.0)
    assert params["a"].max_val == pytest.approx(1.0)
    assert params["a"].default == pytest.approx(0.0)
    assert params["a"].step == pytest.approx(0.1)

    assert params["b"].min_val == pytest.approx(10.0)
    assert params["b"].max_val == pytest.approx(20.0)
    assert params["b"].default == pytest.approx(15.0)
    assert params["b"].step == pytest.approx(0.5)


def test_solve_rejects_invalid_parameter_range(qapp):
    panel = CustomPanel()

    _set_equations(panel, ("a * x", "y", "z"))
    panel._on_compile()

    panel._range_widgets["a"][0].setValue(10.0)
    panel._range_widgets["a"][1].setValue(5.0)

    emitted = []
    panel.compile_requested.connect(emitted.append)

    panel._on_solve()

    assert emitted == []
    assert not panel.status_label.isHidden()
    assert panel.status_label.text() == "Invalid range for a: min must be less than max"
