from pyqtgraph.Qt import QtWidgets


class WorkspacePanel(QtWidgets.QWidget):
    def __init__(self, console_panel, parent=None):
        super().__init__(parent)
        self.console_panel = console_panel

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(console_panel, 1)

        self.set_mode("system")

    def set_mode(self, mode):
        key = str(mode).strip().lower()
        if key not in {"system", "explore"}:
            raise ValueError("Workspace mode must be 'system' or 'explore'")

        self.console_panel.set_explore_visible(key == "explore")
