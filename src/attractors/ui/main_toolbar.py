# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .icons import icon
from .style import MODE_TOOLBAR, SCENE_TOOLBAR, VIEWPORT_TOOLBAR


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


def _spacer(horizontal=True):
    spacer = QtWidgets.QWidget()
    expanding = QtWidgets.QSizePolicy.Policy.Expanding
    preferred = QtWidgets.QSizePolicy.Policy.Preferred
    if horizontal:
        spacer.setSizePolicy(expanding, preferred)
    else:
        spacer.setSizePolicy(preferred, expanding)
    return spacer


class _Toolbar(QtWidgets.QToolBar):
    def __init__(self, title, name, icon_size, style, parent=None):
        super().__init__(title, parent)
        self.setObjectName(name)
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.setStyleSheet(style)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def _add(self, *args, **kwargs):
        action = make_action(self, *args, **kwargs)
        self.addAction(action)
        return action

    def no_focus(self, action):
        self.widgetForAction(action).setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)


class MainToolbar(_Toolbar):
    def __init__(self, system_selector, parent=None):
        super().__init__("Scene", "sceneToolbar", 20, SCENE_TOOLBAR, parent)

        self.left_panel_action = self._add(
            "Left panel", "sidebar-expand-left", tooltip="Toggle sidebar", checked=True
        )
        self.no_focus(self.left_panel_action)
        self.addSeparator()
        sidebar_actions = self.actions()

        self.addWidget(QtWidgets.QLabel(" System: "))
        system_selector.setMinimumWidth(150)
        self.addWidget(system_selector)

        self.solve_action = self._add("Solve", "system-run", tooltip="Run a full solve")
        self.widgetForAction(self.solve_action).setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.reset_action = self._add(
            "Reset", "view-refresh", tooltip="Reset parameters"
        )
        self.addSeparator()
        self.viewport_actions = self.actions()[len(sidebar_actions):]

        self.system_action = make_action(
            self,
            "System",
            "scripting-panels",
            tooltip="Toggle system console",
            checked=False,
        )

        self.viewport_actions.append(self.addWidget(_spacer()))
        self.right_panel_action = self._add(
            "Right panel",
            "sidebar-expand-right",
            tooltip="Toggle right panel",
            checked=True,
        )
        self.no_focus(self.right_panel_action)
        self.viewport_actions.append(self.right_panel_action)


class ViewportToolbar(_Toolbar):
    def __init__(self, parent=None):
        super().__init__("Viewport", "viewportToolbar", 16, VIEWPORT_TOOLBAR, parent)

        self.anim_action = self._add(
            "Play", "media-playback-start", tooltip="Play animation"
        )
        self.loop_action = self._add(
            "Loop animation",
            "media-playlist-repeat",
            tooltip="Loop animation",
            checked=False,
        )
        self.addSeparator()

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
        self.hover_action = self._add(
            "Show coords",
            "crosshairs",
            tooltip="Show trajectory coordinates on hover",
            checked=False,
        )
        self.addSeparator()

        self.reset_camera_action = self._add(
            "Reset camera", "zoom-original", tooltip="Reset camera"
        )
        self.fit_camera_action = self._add(
            "Fit", "view-fullscreen", tooltip="Fit view to trajectories"
        )
        self.auto_fit_camera_action = self._add(
            "Auto fit view to trajectories", "zoom-fit-best", checked=True
        )
        self.orbit_action = self._add(
            "Orbit",
            "object-rotate-right",
            tooltip="Orbit camera automatically",
            checked=False,
        )

        self.addWidget(_spacer())
        self.save_view_action = self._add(
            "Save", "document-save", tooltip="Save view as PNG"
        )

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

    def set_playing(self, playing):
        text = "Pause" if playing else "Play"
        self.anim_action.setIcon(
            icon("media-playback-pause" if playing else "media-playback-start")
        )
        self.anim_action.setText(text)
        self.anim_action.setToolTip(f"{text} animation")


class ModeToolbar(_Toolbar):
    def __init__(
        self,
        workspace_actions,
        scripting_action,
        analysis_actions,
        output_action,
        theme_actions,
        parent=None,
    ):
        super().__init__("Modes", "modeToolbar", 20, MODE_TOOLBAR, parent)
        self.setOrientation(QtCore.Qt.Orientation.Vertical)

        for mode, icon_name in (
            ("explore", "workspace-explore"),
            ("system", "workspace-system"),
        ):
            action = workspace_actions[mode]
            action.setIcon(icon(icon_name))
            action.setToolTip(f"{action.text()} workspace")
            self.addAction(action)

        self.addAction(scripting_action)
        self._system_actions = [scripting_action, self.addSeparator()]
        for action, icon_name in analysis_actions:
            action.setIcon(icon(icon_name))
            self.addAction(action)
            self._system_actions.append(action)

        self.addWidget(_spacer(horizontal=False))
        self.addAction(output_action)

        theme_menu = QtWidgets.QMenu(self)
        theme_menu.addActions(list(theme_actions.values()))
        theme_button = QtWidgets.QToolButton()
        theme_button.setObjectName("modeMenuButton")
        theme_button.setIcon(icon("theme"))
        theme_button.setToolTip("Plot theme")
        theme_button.setMenu(theme_menu)
        theme_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.addWidget(theme_button)

        for action in self.actions():
            widget = self.widgetForAction(action)
            if widget is not None:
                widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def set_system_mode(self, system_mode):
        for action in self._system_actions:
            action.setVisible(system_mode)
