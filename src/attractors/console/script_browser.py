import shutil
from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


def default_scripts_dir():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return Path(app_data) / "scripts"

    return Path(QtCore.QDir.homePath()) / ".strange-attractors" / "scripts"


class ScriptBrowser(QtWidgets.QWidget):
    script_selected = QtCore.pyqtSignal(object)
    path_renamed = QtCore.pyqtSignal(object, object)
    path_deleted = QtCore.pyqtSignal(object)

    def __init__(self, scripts_dir, parent=None):
        super().__init__(parent)
        self.scripts_dir = (
            Path(scripts_dir) if scripts_dir is not None else default_scripts_dir()
        )
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._selecting = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.new_script_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("document-new"), "New"
        )
        self.new_script_action.setToolTip("Create a new script")
        self.new_folder_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("folder-new"), "New Folder"
        )
        self.new_folder_action.setToolTip("Create a new folder")
        self.rename_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("edit-rename"), "Rename"
        )
        self.rename_action.setToolTip("Rename the selected script or folder")
        self.delete_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("edit-delete"), "Delete"
        )
        self.delete_action.setToolTip("Delete the selected script or folder")

        self.model = QtGui.QFileSystemModel(self)
        self.model.setReadOnly(False)
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
        self.rename_action.triggered.connect(self._rename_selected)
        self.delete_action.triggered.connect(self._delete_selected)

    def select_path(self, path):
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
        self.select_path(path)
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

    def _selected_path(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return None

        return Path(self.model.filePath(index))

    def _rename_selected(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        path = Path(self.model.filePath(index))
        if path == self.scripts_dir:
            return

        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            text=path.name,
        )

        if not accepted:
            return

        name = name.strip()
        if not name:
            return

        if path.is_file():
            name = self._normalise_script_name(name)

        new_path = path.with_name(name)

        if new_path == path:
            return

        if not self._validate_new_path(new_path):
            return

        try:
            renamed = self.model.setData(
                index,
                name,
                QtCore.Qt.ItemDataRole.EditRole,
            )
        except OSError as e:
            self._show_error(str(e))
            return

        if not renamed:
            self._show_error(f"Could not rename {path}")
            return

        self.path_renamed.emit(path, new_path)
        QtCore.QTimer.singleShot(0, lambda path=new_path: self.select_path(path))

    def _delete_selected(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        path = self._selected_path()
        if path is None or path == self.scripts_dir:
            return

        if path.is_dir():
            message = f"Delete folder '{path.name}' and all its contents?"
        else:
            message = f"Delete script '{path.name}'?"

        result = QtWidgets.QMessageBox.question(
            self,
            "Delete",
            message,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if result != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                deleted = self.model.remove(index)
                if not deleted:
                    self._show_error(f"Could not delete {path}")
                    return
            else:
                self._show_error(f"Path does not exist: {path}")
                return
        except OSError as e:
            self._show_error(str(e))
            return

        self.path_deleted.emit(path)

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

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        self._update_toolbar_style()

    def _update_toolbar_style(self):
        style = (
            QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
            if self.toolbar.width() < 250
            else QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toolbar.setToolButtonStyle(style)
