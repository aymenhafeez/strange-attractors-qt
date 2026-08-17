import numpy as np
import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.console.view3d import (
    ConsoleView3D,
    ConsoleView3DManager,
    check_points,
    normalise_colour,
    normalise_size,
)
from attractors.ui.docking import AreaBoundDock, AreaBoundDockArea


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    return app


def test_check_points_valid_inputs():
    points = check_points([[1, 2, 3], [4, 5, 6]])
    split = check_points([1, 4], [2, 5], [3, 6])

    assert points.shape == (2, 3)
    np.testing.assert_allclose(points, split)


@pytest.mark.parametrize(
    "args, match",
    [
        (([[1, 2]],), "shape"),
        (([1, 2], [3], [4, 5]), "same length"),
        (([[1, 2, np.nan]],), "non finite"),
        (([],), "shape"),
    ],
)
def test_check_points_invalid_inputs(args, match):
    with pytest.raises(ValueError, match=match):
        check_points(*args)


def test_normalise_colours_input_kind():
    assert normalise_colour("red") == (1.0, 0.0, 0.0, 1.0)
    assert normalise_colour("#00ff00") == (0.0, 1.0, 0.0, 1.0)
    assert normalise_colour((0.1, 0.2, 0.3)) == (0.1, 0.2, 0.3, 1.0)
    assert normalise_colour((0.1, 0.2, 0.3, 0.4)) == (0.1, 0.2, 0.3, 0.4)

    colours = normalise_colour([[1, 0, 0], [0, 1, 0]])
    assert colours.shape == (2, 4)
    np.testing.assert_allclose(colours[:, 3], [1, 1])


def test_normalise_colours_invalid_inputs():
    with pytest.raises(ValueError, match="Invalid colour"):
        normalise_colour("sldkfsdfkj")

    with pytest.raises(ValueError, match="Colour must"):
        normalise_colour([[1, 2], [3, 4]])


@pytest.mark.parametrize(
    "size, match",
    [
        ([[1, 2], [3, 4]], "number or 1D array"),
        ([1, 2], "same length"),
        ([1, np.inf, 3], "non finite"),
    ],
)
def test_normalise_size_invalid_inputs(size, match):
    with pytest.raises(ValueError, match=match):
        normalise_size(size, 3)


def test_view3d_manager_create_rename_close(qapp):
    dock_area = AreaBoundDockArea()
    default_view = ConsoleView3D()
    default_dock = AreaBoundDock("3D View", closable=False)
    default_dock.addWidget(default_view.host)
    dock_area.addDock(default_dock)

    manager = ConsoleView3DManager(dock_area, "3D View", default_view, default_dock)

    created = manager.new("Test View")
    same = manager.new("Test View")

    assert same == created
    assert manager.current_name == "Test View"
    assert manager.names() == ["3D View", "Test View"]

    manager.rename("Test View", "New Test View")

    assert manager.current_name == "New Test View"
    assert manager.names() == ["3D View", "New Test View"]

    with pytest.raises(ValueError, match="already exists"):
        manager.rename("New Test View", "3D View")

    manager.close("New Test View")

    assert manager.names() == ["3D View"]
    assert manager.current_name == "3D View"


def test_view3d_manager_replace_and_overlay(qapp):
    view = ConsoleView3D()
    first = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float64)
    second = np.array([[1, 0, 0], [0, 1, 1]], dtype=np.float64)

    view.explore.line3d("first", first)
    assert view.explore.trace_names() == ["first"]

    view.explore.line3d("second", second, mode="overlay")
    assert view.explore.trace_names() == ["first", "second"]

    view.explore.line3d("replace", second, mode="replace")
    assert view.explore.trace_names() == ["replace"]
    assert len(view._items) == 1
