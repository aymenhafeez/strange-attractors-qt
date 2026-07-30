from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


def _default_scripts_dir():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return Path(app_data) / "scripts"

    return Path(QtCore.QDir.homePath()) / ".strange-attractors" / "scripts"


class ScriptBrowser(QtWidgets.QWidget):
    script_selected = QtCore.pyqtSignal(object)

    def __init__(self, scripts_dir, parent=None):
        super().__init__(parent)
        self.scripts_dir = (
            Path(scripts_dir) if scripts_dir is not None else _default_scripts_dir()
        )
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._selecting = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.new_script_action = self.toolbar.addAction("New")
        self.new_script_action.setToolTip("Create a new script")
        self.new_folder_action = self.toolbar.addAction("New Folder")
        self.new_folder_action.setToolTip("Create a new folder")

        self.model = QtGui.QFileSystemModel(self)
        self.model.setRootPath(str(self.scripts_dir))
        self.model.setNameFilters(["*.py"])
        self.model.setNameFilterDisables(False)

        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(self.scripts_dir)))
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )

        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.tree)

        self.tree.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )

        self.new_script_action.triggered.connect(self._new_script)
        self.new_folder_action.triggered.connect(self._new_folder)

    def select_script(self, path):
        if path is None:
            return

        index = self.model.index(str(path))
        if not index.isValid():
            return

        self._selecting = True
        try:
            self.tree.setCurrentIndex(index)
            self.tree.scrollTo(index)
        finally:
            self._selecting = False

    def _on_tree_selection_changed(self, current, _previous):
        if self._selecting:
            return

        path = Path(self.model.filePath(current))
        if path.is_file() and path.suffix == ".py":
            self.script_selected.emit(path)

    def _new_script(self):
        parent = self._selected_directory()
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "New script",
            "Script name:",
            text=self._next_script_name(parent),
        )

        if not accepted:
            return

        name = self._normalise_script_name(name)
        if not name:
            return

        path = parent / name
        if not self._validate_new_path(path):
            return

        path.write_text("", encoding="utf-8")
        self.select_script(path)
        self.script_selected.emit(path)

    def _new_folder(self):
        parent = self._selected_directory()
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "New folder",
            "Folder name:",
            text=self._next_folder_name(parent),
        )

        if not accepted:
            return

        name = name.strip()
        if not name:
            return

        path = parent / name
        if not self._validate_new_path(path):
            return

        path.mkdir()
        index = self.model.index(str(path))
        if index.isValid():
            self.tree.setCurrentIndex(index)
            self.tree.expand(index)

    def _selected_directory(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return self.scripts_dir

        path = Path(self.model.filePath(index))
        if path.is_dir():
            return path

        return path.parent

    def _normalise_script_name(self, name):
        name = name.strip()
        if not name:
            return ""

        if not name.endswith(".py"):
            name += ".py"

        return name

    def _validate_new_path(self, path):
        try:
            self._resolve_child_path(path)
        except ValueError as e:
            self._show_error(str(e))
            return False

        if path.exists():
            self._show_error(f"Path already exists: {path}")
            return False

        return True

    def _resolve_child_path(self, path):
        root = self.scripts_dir.resolve()
        path = Path(path).resolve()

        if path != root and root not in path.parents:
            raise ValueError(f"Path {path} is outside of scripts directory")

        return path

    def _next_script_name(self, parent):
        return self._next_available_name(parent, "untitled", ".py")

    def _next_folder_name(self, parent):
        return self._next_available_name(parent, "New Folder", "")

    def _next_available_name(self, parent, stem, suffix):
        first = f"{stem}{suffix}"

        if not (parent / first).exists():
            return first

        index = 2
        while True:
            name = f"{stem} {index}{suffix}"
            if not (parent / name).exists():
                return name
            index += 1

    def _show_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)
