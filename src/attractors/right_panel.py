from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .preset_panel import PresetPanel
from .style import SIDE_PANEL
from .trajectory_panel import TrajectoryPanel


class _CollapsibleSection(QtWidgets.QWidget):
    def __init__(self, title, widget, parent=None, *, expanded=True):
        super().__init__(parent)
        self._title = str(title)
        self._widget = widget

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self.toggle_btn = QtWidgets.QPushButton()
        self.toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_btn)

        self._content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(widget)
        layout.addWidget(self._content)

        self.set_expanded(expanded)

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        self._content.setVisible(expanded)
        marker = "▾" if expanded else "▸"
        self.toggle_btn.setText(f"{self._title} {marker}")

    def toggle(self):
        self.set_expanded(not self._content.isVisible())
        self.adjustSize()


class RightPanel(QtWidgets.QWidget):
    def __init__(self, scripts_dir=None, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(260)
        self.setStyleSheet(SIDE_PANEL)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 4, 4)
        layout.setSpacing(0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("sidePanelScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.scroll)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content)

        self.trajectory_panel = TrajectoryPanel()
        self.preset_panel = PresetPanel()
        self.custom_panel = CustomPanel()
        self.preset_section = _CollapsibleSection(
            "Presets",
            self.preset_panel,
            expanded=True,
        )

        self.content_layout.addWidget(self.trajectory_panel)
        self.content_layout.addWidget(self.preset_section)
        self.content_layout.addWidget(self.custom_panel)
        self.content_layout.addStretch(1)

        self._set_panel_expanded(self.trajectory_panel, True)
        self._set_panel_expanded(self.custom_panel, False)
        self.set_current_attractor("")

    def set_current_attractor(self, name):
        custom = name == "Custom"
        self.custom_panel.setVisible(custom)
        if custom:
            self._set_panel_expanded(self.custom_panel, True)

    def _set_panel_expanded(self, panel, expanded):
        content = getattr(panel, "_content", None)
        toggle_btn = getattr(panel, "toggle_btn", None)
        if content is None or toggle_btn is None:
            return

        expanded = bool(expanded)
        content.setVisible(expanded)
        title = toggle_btn.text().split(" ", 1)[0]
        marker = "▾" if expanded else "▸"
        toggle_btn.setText(f"{title} {marker}")
