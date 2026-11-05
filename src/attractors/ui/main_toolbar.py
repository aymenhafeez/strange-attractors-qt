# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .icons import icon
from .style import SCENE_TOOLBAR


def make_action(parent, text, icon_name=None, *, tooltip=None, checked=None):
    action = QtGui.QAction(text, parent)
    if icon_name is not None:
        action.setIcon(icon(icon_name))
    if tooltip is not None:
        action.setToolTip(tooltip)
    if checked is not None:
        action.setCheckable(True)
        action.setChecked(checked)

    return action


class MainToolbar(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__("Scene", parent)
        self.setObjectName("sceneToolbar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(22, 22))
        self.setStyleSheet(SCENE_TOOLBAR)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.left_panel_action = self._add(
            "Left panel", "sidebar-expand-left", tooltip="Show left panel", checked=True
        )
        self.no_focus(self.left_panel_action)
        self.anim_action = self._add(
            "Play", "media-playback-start", tooltip="Play animation"
        )
        self.loop_action = self._add(
            "Loop animation",
            "media-playlist-repeat",
            tooltip="Loop animation",
            checked=False,
        )
        self.reset_action = self._add(
            "Reset", "view-refresh", tooltip="Reset parameters"
        )
        self.reset_camera_action = self._add(
            "Reset camera", "zoom-original", tooltip="Reset camera"
        )
        self.fit_camera_action = self._add(
            "Fit", "view-fullscreen", tooltip="Fit view to trajectories"
        )
        self.auto_fit_camera_action = self._add(
            "Auto fit view to trajectories", "zoom-fit-best", checked=True
        )
        self.save_view_action = self._add(
            "Save", "document-save", tooltip="Save view as PNG"
        )
        self.point_action = self._add(
            "Show leading point",
            "media-record",
            tooltip="Show animation head points",
            checked=True,
        )
        self.line_action = self._add(
            "Show lines", "draw-line", tooltip="Show trajectory lines", checked=False
        )
        self.trail_action = self._add(
            "Show trail",
            "draw-path",
            tooltip="Show animated trajectory trails",
            checked=False,
        )
        self.grid_action = self._add(
            "Grid", "view-grid", tooltip="Show grid", checked=True
        )
        self.orbit_action = self._add(
            "Orbit",
            "object-rotate-right",
            tooltip="Orbit camera automatically",
            checked=False,
        )
        self.hover_action = self._add(
            "Show coords",
            "crosshairs",
            tooltip="Show trajectory coordinates on hover",
            checked=False,
        )
        self.solve_action = self._add("Solve", "system-run", tooltip="Run a full solve")
        self.addSeparator()

        self.scene_actions = (
            self.anim_action,
            self.loop_action,
            self.point_action,
            self.line_action,
            self.trail_action,
            self.grid_action,
            self.orbit_action,
            self.hover_action,
            self.reset_camera_action,
            self.fit_camera_action,
            self.auto_fit_camera_action,
            self.save_view_action,
        )
        self.viewport_actions = self.actions()

        self.system_action = self._add(
            "System",
            "preferences-system-symbolic",
            tooltip="Show or hide system scripting panels",
            checked=False,
        )
        self.explore_action = self._add("Explore", "gnumeric-graphguru", checked=False)
        self.addSeparator()

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.viewport_actions.append(self.addWidget(spacer))

        self.right_panel_action = self._add(
            "Right panel",
            "sidebar-expand-right",
            tooltip="Show right panel",
            checked=True,
        )
        self.no_focus(self.right_panel_action)
        self.viewport_actions.append(self.right_panel_action)

        end_pad = QtWidgets.QWidget()
        end_pad.setFixedWidth(3)
        self.addWidget(end_pad)

    def _add(self, *args, **kwargs):
        action = make_action(self, *args, **kwargs)
        self.addAction(action)
        return action

    def no_focus(self, action):
        self.widgetForAction(action).setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def set_playing(self, playing):
        text = "Pause" if playing else "Play"
        self.anim_action.setIcon(
            icon("media-playback-pause" if playing else "media-playback-start")
        )
        self.anim_action.setText(text)
        self.anim_action.setToolTip(f"{text} animation")
