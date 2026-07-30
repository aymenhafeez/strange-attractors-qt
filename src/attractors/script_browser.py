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

        self.model = QtGui.QFileSystemModel(self)
        self.model.setRootPath(str(self.scripts_dir))
        self.model.setNameFilters(["*.py"])
        self.model.setNameFilterDisables(False)

        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(self.scripts_dir)))
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)

        layout.addWidget(self.tree)

        self.tree.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )

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
