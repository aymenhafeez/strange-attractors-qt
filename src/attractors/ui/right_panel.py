# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .preset_panel import PresetPanel
from .trajectory_panel import TrajectoryPanel


def _scrollable(widget):
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setMinimumWidth(230)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)

    return scroll


class RightPanel(QtCore.QObject):
    def __init__(self, dock_layout):
        super().__init__(dock_layout)
        self.trajectory_panel = TrajectoryPanel(collapsible=False)
        self.trajectory_panel.setMinimumWidth(230)
        self.preset_panel = PresetPanel()
        self.custom_panel = CustomPanel(collapsible=False)

        self.trajectory_dock = dock_layout.add(
            "trajectories", "Trajectories", self.trajectory_panel
        )
        self.preset_dock = dock_layout.add(
            "presets", "Presets", _scrollable(self.preset_panel)
        )
        self.custom_dock = dock_layout.add(
            "custom", "Custom", _scrollable(self.custom_panel)
        )

    def set_current_attractor(self, name):
        if name == "Custom":
            self.custom_dock.raise_()
        else:
            self.preset_dock.raise_()
