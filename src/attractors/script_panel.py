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

        self.run_action = self.toolbar.addAction("Run")
        self.run_action.setToolTip("Run script")
        self.save_action = self.toolbar.addAction("Save")
        self.save_action.setToolTip("Save script")

        self.status_label = QtWidgets.QLabel()
        self.status_label.setMinimumWidth(120)
        self.toolbar.addWidget(self.status_label)

        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setTabStopDistance(
            self.editor.fontMetrics().horizontalAdvance(" ") * 4
        )

        layout.addWidget(self.toolbar)
        layout.addWidget(self.editor, 1)

        self.run_action.triggered.connect(self.run)
        self.save_action.triggered.connect(self.save)

        self.load()

    def load(self):
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        if self.script_path.exists():
            self.editor.setPlainText(self.script_path.read_text(encoding="utf-8"))
            self.status_label.setText(f"Saved {self.script_path.name}")

    def save(self):
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.script_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        self.status_label.setText(f"Saved {self.script_path.name}")

    def run(self):
        self.save()
        self.run_requested.emit(self.editor.toPlainText())
        self.status_label.setText(f"Ran {self.script_path.name}")
