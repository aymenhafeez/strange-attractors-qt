import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.bifurcation_panel import BifurcationPanel


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_cancel_sweep_marks_worker_cancelled_and_clears_reference(qapp):
    panel = BifurcationPanel()

    class Worker:
        _cancel = False

    worker = Worker()
    panel._worker = worker
    panel.run_btn.setEnabled(False)
    panel.cancel_btn.setEnabled(True)

    panel.cancel_sweep()

    assert worker._cancel is True
    assert panel._worker is None
    assert panel.run_btn.isEnabled()
    assert not panel.cancel_btn.isEnabled()
