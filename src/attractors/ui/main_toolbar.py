from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .style import SCENE_TOOLBAR


def build_toolbar(self):
    toolbar = QtWidgets.QToolBar("Scene")
    toolbar.setObjectName("sceneToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setIconSize(QtCore.QSize(18, 18))
    toolbar.setStyleSheet(SCENE_TOOLBAR)
    self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)
    self.scene_toolbar = toolbar

    style_icon = QtWidgets.QStyle.StandardPixmap

    start_pad = QtWidgets.QWidget()
    start_pad.setFixedWidth(3)
    toolbar.addWidget(start_pad)

    self.toolbar_left_panel_action = self._add_checked_icon_toolbar_action(
        toolbar,
        self._side_panel_icon("left"),
        True,
        lambda checked: self._set_left_panel_visible(checked),
        "Show left panel",
    )
    toolbar.addSeparator()

    self.toolbar_anim_action = toolbar.addAction(
        self.style().standardIcon(style_icon.SP_MediaPlay),
        "Play",
        lambda: self._sync_toolbar_animation_action(
            self.scene.animation_controller.toggle()
        ),
    )
    self.toolbar_anim_action.setToolTip("Play animation")

    self.toolbar_loop_action = self._add_checked_toolbar_action(
        toolbar,
        "Loop",
        False,
        self.scene.animation_controller.set_loop,
        "Loop animation",
        icon=self._toolbar_icon(
            "media-playlist-repeat",
            QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
        ),
    )

    toolbar.addSeparator()

    self.toolbar_reset_action = toolbar.addAction(
        self.style().standardIcon(style_icon.SP_BrowserReload), "Reset"
    )
    self.toolbar_reset_action.setToolTip("Reset parameters")
    self.toolbar_reset_action.triggered.connect(self.controls.reset_to_defaults)

    self.toolbar_reset_camera_action = toolbar.addAction(
        QtGui.QIcon.fromTheme("zoom-original"),
        "Reset camera",
        self._reset_camera,
    )
    self.toolbar_reset_camera_action.setToolTip("Reset camera")

    self.toolbar_fit_camera_action = toolbar.addAction(
        QtGui.QIcon.fromTheme("view-fullscreen"),
        "Fit",
        lambda: self.scene.camera_controller.fit_camera_to_solutions(
            self.scene.trajectory_renderer.solutions
        ),
    )
    self.toolbar_fit_camera_action.setToolTip("Fit view to trajectories")

    self.toolbar_auto_fit_camera_action = toolbar.addAction(
        QtGui.QIcon.fromTheme("zoom-fit-best"), "Auto fit view to trajectories"
    )
    self.toolbar_auto_fit_camera_action.setCheckable(True)
    self.toolbar_auto_fit_camera_action.setChecked(self.auto_fit_camera)
    self.toolbar_auto_fit_camera_action.toggled.connect(
        lambda enabled: setattr(self, "auto_fit_camera", enabled)
    )

    self.toolbar_save_view_action = toolbar.addAction(
        self.style().standardIcon(style_icon.SP_DialogSaveButton),
        "Save",
        self.scene.viewport_overlay.save_view_as_png,
    )
    self.toolbar_save_view_action.setToolTip("Save view as PNG")

    toolbar.addSeparator()

    self.toolbar_point_action = self._add_checked_toolbar_action(
        toolbar,
        "Point",
        True,
        self.scene.trajectory_renderer.set_point_mode,
        "Show animation head points",
        icon=self._toolbar_icon(
            "media-record",
            QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton,
        ),
    )
    self.toolbar_line_action = self._add_checked_toolbar_action(
        toolbar,
        "Line",
        False,
        lambda checked: self._set_line_mode(checked),
        "Show trajectory lines",
        icon=self._toolbar_icon(
            "draw-line",
            QtWidgets.QStyle.StandardPixmap.SP_FileDialogListView,
        ),
    )
    self.toolbar_trail_action = self._add_checked_toolbar_action(
        toolbar,
        "Trail",
        False,
        self._set_trail_mode,
        "Show animated trajectory trails",
        icon=self._toolbar_icon(
            "draw-path",
            QtWidgets.QStyle.StandardPixmap.SP_ArrowRight,
        ),
    )
    self.toolbar_grid_action = self._add_checked_toolbar_action(
        toolbar,
        "Grid",
        True,
        self.scene.grid_overlay.set_grid_visible,
        "Show grid",
        icon=self._toolbar_icon(
            "view-grid",
            QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
        ),
    )
    self.toolbar_orbit_action = self._add_checked_toolbar_action(
        toolbar,
        "Orbit",
        False,
        self._set_orbit_mode,
        "Orbit camera automatically",
        icon=self._toolbar_icon(
            "object-rotate-right",
            QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
        ),
    )

    toolbar.addSeparator()

    self.toolbar_solve_action = toolbar.addAction(
        self._toolbar_icon(
            "system-run",
            QtWidgets.QStyle.StandardPixmap.SP_MediaPlay,
        ),
        "Solve",
    )
    self.toolbar_solve_action.setToolTip("Run a full solve")
    self.toolbar_solve_action.triggered.connect(
        lambda: self._on_controls_solve_requested(True)
    )

    self.toolbar_lyapunov_action = self._add_panel_menu_action(
        "Lyapunov spectrum",
        self._toggle_lyapunov_panel,
    )
    self.toolbar_projection_action = self._add_panel_menu_action(
        "Projection heatmaps",
        self._toggle_projections,
    )
    self.toolbar_poincare_action = self._add_panel_menu_action(
        "Poincare section",
        self._toggle_poincare,
    )
    self.toolbar_bifurcation_action = self._add_panel_menu_action(
        "Bifurcation diagram",
        self._toggle_bifurcation,
    )
    self.toolbar_jupyter_console_action = self._add_panel_menu_action(
        "System workspace",
        self._toggle_jupyter_console,
    )
    self.toolbar_process_status_action = self._add_panel_menu_action(
        "Status bar",
        lambda: self._toggle_process_status(),
    )

    toolbar.addSeparator()
    spacer = QtWidgets.QWidget()
    spacer.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Preferred,
    )
    toolbar.addWidget(spacer)

    self.system_toolbar_action = toolbar.addWidget(self.system_toolbar)
    self._jupyter_toolbar_actions.append(self.system_toolbar_action)

    # spacer = QtWidgets.QWidget()
    # spacer.setSizePolicy(
    #     QtWidgets.QSizePolicy.Policy.Expanding,
    #     QtWidgets.QSizePolicy.Policy.Preferred,
    # )
    # toolbar.addWidget(spacer)

    toolbar.addSeparator()
    self._build_jupyter_toolbar_actions(toolbar)
    self.toolbar_right_panel_action = self._add_checked_icon_toolbar_action(
        toolbar,
        self._side_panel_icon("right"),
        True,
        lambda checked: self._set_right_panel_visible(checked),
        "Show right panel",
    )
    end_pad = QtWidgets.QWidget()
    end_pad.setFixedWidth(3)
    toolbar.addWidget(end_pad)

    self._sync_toolbar_panel_actions()
