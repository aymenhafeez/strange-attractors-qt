from pathlib import Path

from pyqtgraph.Qt import QtCore, QtWidgets

from .syntax import PythonHighlighter


def _default_scripts_dir():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return Path(app_data) / "scripts"

    return Path(QtCore.QDir.homePath()) / ".strange-attractors" / "scripts"


class ScriptStore:
    def __init__(self, root):
        self.root = Path(root) if root is not None else _default_scripts_dir()

    def ensure_root(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_script(self, path):
        path = Path(path).resolve()
        root = self.root.resolve()

        if root != path and root not in path.parents:
            raise ValueError(f"Script path {path} is outside of scripts directory")
        if path.suffix != ".py":
            raise ValueError("Script is not a Python file")

        return path

    def read(self, path):
        return self.resolve_script(path).read_text(encoding="utf-8")

    def write(self, path, text):
        path = self.resolve_script(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file = QtCore.QSaveFile(str(path))
        if not file.open(
            QtCore.QIODevice.OpenModeFlag.WriteOnly | QtCore.QIODevice.OpenModeFlag.Text
        ):
            raise OSError(file.errorString())

        file.write(text.encode("utf-8"))

        if not file.commit():
            raise OSError(file.errorString())


class ScriptPanel(QtWidgets.QWidget):
    run_requested = QtCore.pyqtSignal(str)
    status_changed = QtCore.pyqtSignal(str)
    script_changed = QtCore.pyqtSignal(object)

    def __init__(self, scripts_dir, parent=None):
        super().__init__(parent)
        self.store = ScriptStore(scripts_dir)
        self.scripts_dir = self.store.root
        self.script_path = self.scripts_dir / "scratch.py"
        self.current_path = None
        self._loading = False
        self._dirty = False

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
        self.highlighter = PythonHighlighter(self.editor.document())

        layout.addWidget(self.toolbar)
        layout.addWidget(self.editor, 1)

        self.editor.textChanged.connect(self._on_editor_text_changed)

        self.run_action.triggered.connect(self.run)
        self.save_action.triggered.connect(self.save)

        self.load()

    def load(self):
        self.store.ensure_root()
        if not self.script_path.exists():
            self.store.write(self.script_path, "")
        self.load_script(self.script_path)

    def load_script(self, path):
        path = self.store.resolve_script(path)
        if path == self.current_path:
            return True
        if not self._confirm_discard_changes():
            return False

        self._loading = True
        try:
            self.editor.setPlainText(self.store.read(path))
            self.current_path = path
            self._dirty = False
            self._update_status("Loaded")
            self.script_changed.emit(path)
        finally:
            self._loading = False

        return True

    def save(self):
        if self.current_path is None:
            self.load()
        self.store.write(self.current_path, self.editor.toPlainText())
        self._dirty = False
        self._update_status("Saved")
        return True

    def run(self):
        self.save()
        self.run_requested.emit(self.editor.toPlainText())
        self._update_status("Ran")

    def _on_editor_text_changed(self):
        if self._loading:
            return

        self._dirty = True
        self._update_status("Modified")

    def _confirm_discard_changes(self):
        if not self._dirty:
            return True

        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved script",
            "Discard unsaved script changes?",
            QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )

        return result == QtWidgets.QMessageBox.StandardButton.Discard

    def _update_status(self, action):
        if self.current_path is None:
            self.status_label.setText("")
            return

        marker = "*" if self._dirty else ""
        text = f"{action} {self.current_path.name}{marker}"
        self.status_label.setText(text)
        self.status_changed.emit(text)
