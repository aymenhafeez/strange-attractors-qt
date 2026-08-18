import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.ui.bifurcation_panel import BifurcationPanel


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_cancel_sweep_cancels_worker(qapp):
    panel = BifurcationPanel()

    class Worker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    worker = Worker()
    panel._worker = worker
    panel.run_btn.setEnabled(False)
    panel.cancel_btn.setEnabled(True)

    panel.cancel_sweep()

    assert worker.cancelled is True
    assert panel._worker is None
    assert panel.run_btn.isEnabled()
    assert not panel.cancel_btn.isEnabled()
