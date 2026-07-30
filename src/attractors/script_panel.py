from pathlib import Path

from pyqtgraph.Qt import QtCore, QtWidgets


class ScriptPanel(QtWidgets.QWidget):
    run_requested = QtCore.pyqtSignal(str)
    status_changed = QtCore.pyqtSignal(str)

    def __init__(self, scripts_dir, parent=None):
        super().__init__(parent)
        self.scripts_dir = Path(scripts_dir)
        self.script_path = self.scripts_dir / "scratch.py"

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
