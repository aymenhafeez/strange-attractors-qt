from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .preset_panel import PresetPanel
from .trajectory_panel import TrajectoryPanel


class RightPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(260)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(False)
        layout.addWidget(self.tabs)

        self.trajectory_panel = TrajectoryPanel(collapsible=False)
        self.preset_panel = PresetPanel()
        self.custom_panel = CustomPanel(collapsible=False)

        self.trajectory_tab_index = self.tabs.addTab(
            self._scroll_tab(self.trajectory_panel), "Trajectories"
        )
        self.preset_tab_index = self.tabs.addTab(
            self._scroll_tab(self.preset_panel), "Presets"
        )
        self.custom_tab_index = self.tabs.addTab(
            self._scroll_tab(self.custom_panel), "Custom"
        )
        self.set_current_attractor("")

    def _scroll_tab(self, widget):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(widget)
        return scroll

    def set_current_attractor(self, name):
        custom = name == "Custom"
        self.tabs.setTabEnabled(self.custom_tab_index, custom)
        self.custom_panel.setVisible(custom)
        if custom:
            self.tabs.setCurrentIndex(self.custom_tab_index)
        elif self.tabs.currentIndex() == self.custom_tab_index:
            self.tabs.setCurrentIndex(self.trajectory_tab_index)
