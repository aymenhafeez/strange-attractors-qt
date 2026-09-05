from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .process_metrics import ProcessUsageStatus
from .style import SCENE_TOOLBAR


def build_status_bar(self):
    status_bar = QtWidgets.QStatusBar()
    status_bar.setSizeGripEnabled(False)
    status_bar.setFixedHeight(18)
    status_bar.setStyleSheet(
        """
        QStatusBar {
            border: none;
            padding: 0px;
        }
        QStatusBar::item {
            border: none;
        }
        """
    )

    self.app_status_label = QtWidgets.QLabel("")
    self.app_status_label.setAlignment(
        QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
    )
    self.app_status_label.setStyleSheet(
        "border: none; padding: 0 4px 1px 4px; font-size: 12px; color: #178640;"
    )
    self.process_status = ProcessUsageStatus()
    status_bar.addWidget(self.app_status_label, 1)
    status_bar.addPermanentWidget(self.process_status)
    self.setStatusBar(status_bar)
    self._set_process_status_visible(self._process_status_visible)


def build_menu_bar(self):
    menu_bar = self.menuBar()
    menu_bar.clear()
    self._menu_actions = []

    file_menu = menu_bar.addMenu("&File")
    file_menu.addAction(
        "Save view as PNG",
        self.scene.viewport_overlay.save_view_as_png,
    )
    file_menu.addSeparator()
    file_menu.addAction("Open preset folder", self._open_preset_folder)

    view_menu = menu_bar.addMenu("&View")
    self._add_menu_action(view_menu, "Left panel", self.toolbar_left_panel_action)
    self._add_menu_action(view_menu, "Right panel", self.toolbar_right_panel_action)
    self._add_menu_action(view_menu, "Status bar", self.toolbar_process_status_action)
    view_menu.addSeparator()
    view_menu.addAction(
        "Reset camera",
        self._reset_camera,
    )
    view_menu.addAction(
        "Fit view",
        lambda: self.scene.camera_controller.fit_camera_to_solutions(
            self.scene.trajectory_renderer.solutions
        ),
    )

    self._add_menu_action(view_menu, "Grid", self.toolbar_grid_action)

    view_menu.addSeparator()

    plot_theme_menu = view_menu.addMenu("Plot theme")
    self.view_system_action = plot_theme_menu.addAction("System")
    self.view_light_action = plot_theme_menu.addAction("Light")
    self.view_dark_action = plot_theme_menu.addAction("Dark")

    theme_group = QtGui.QActionGroup(self)
    theme_group.setExclusive(True)
    for action in (
        self.view_system_action,
        self.view_light_action,
        self.view_dark_action,
    ):
        action.setCheckable(True)
        theme_group.addAction(action)

    self.view_system_action.setChecked(True)

    self.view_system_action.triggered.connect(lambda: self._set_theme(None))
    self.view_light_action.triggered.connect(lambda: self._set_theme("light"))
    self.view_dark_action.triggered.connect(lambda: self._set_theme("dark"))

    view_menu.addSeparator()
    view_menu.addAction("Reset session state", self._reset_session_state)

    system_menu = menu_bar.addMenu("&System")
    system_menu.addAction("Solve", lambda: self._on_controls_solve_requested(True))
    system_menu.addAction(
        "Reset parameters",
        self.controls.reset_to_defaults,
    )
    system_menu.addSeparator()

    animation_mode_menu = system_menu.addMenu("Animation mode")

    self.animation_mode_group = QtGui.QActionGroup(self)
    self.animation_mode_group.setExclusive(True)

    self.animation_traj_action = animation_mode_menu.addAction("Trajectory")
    self.animation_particle_flow_action = animation_mode_menu.addAction("Particle flow")

    for action in (self.animation_traj_action, self.animation_particle_flow_action):
        action.setCheckable(True)
        self.animation_mode_group.addAction(action)

    self.animation_traj_action.setChecked(True)

    self.animation_traj_action.triggered.connect(
        lambda checked: self._set_animation_mode("trajectory") if checked else None
    )
    self.animation_particle_flow_action.triggered.connect(
        lambda checked: self._set_animation_mode("particle") if checked else None
    )

    system_menu.addSeparator()

    self._add_menu_action(system_menu, "Loop animation", self.toolbar_loop_action)
    self._add_menu_action(system_menu, "Show leading point", self.toolbar_point_action)
    self._add_menu_action(system_menu, "Show lines", self.toolbar_line_action)
    self._add_menu_action(system_menu, "Show trail", self.toolbar_trail_action)

    workspace_menu = menu_bar.addMenu("&Workspace")
    mode_menu = workspace_menu.addMenu("Mode")
    mode_group = QtGui.QActionGroup(self)
    mode_group.setExclusive(True)
    self.workspace_system_mode_action = mode_menu.addAction("System")
    self.workspace_system_mode_action.setCheckable(True)
    self.workspace_system_mode_action.setChecked(True)
    self.workspace_explore_mode_action = mode_menu.addAction("Explore")
    self.workspace_explore_mode_action.setCheckable(True)
    mode_group.addAction(self.workspace_system_mode_action)
    mode_group.addAction(self.workspace_explore_mode_action)
    self.workspace_system_mode_action.triggered.connect(
        lambda: self._set_workspace_mode("system")
    )
    self.workspace_explore_mode_action.triggered.connect(
        lambda: self._set_workspace_mode("explore")
    )
    workspace_menu.addSeparator()
    workspace_menu.addAction("Summary", self.show_workspace_summary)
    workspace_menu.addAction(
        "Explore workspace", lambda: self._set_workspace_mode("explore")
    )
    workspace_menu.addAction("Restore Explore layout", self._restore_explore_layout)
    examples_menu = workspace_menu.addMenu("Examples")
    self._populate_examples_menu(examples_menu)
    workspace_menu.addSeparator()
    workspace_menu.addAction("New plot", self.workspace_controller.new_plot)
    workspace_menu.addAction(
        "Clear current view",
        self.workspace_controller.clear_current_view,
    )
    workspace_menu.addAction("Export current table", self._export_current_table)
    workspace_menu.addAction(
        "Clear all views", self.workspace_controller.clear_all_views
    )
    workspace_menu.addSeparator()
    workspace_menu.addAction("Clear sliders", self._clear_current_explore_sliders)
    workspace_menu.addAction("Clear traces", self._clear_current_explore_traces)
    workspace_menu.addAction("Clear explore state", self._clear_current_explore)
    workspace_menu.addSeparator()
    self._add_menu_action(workspace_menu, "View all", self.plot_view_all_action)
    self._add_menu_action(workspace_menu, "Pan", self.plot_pan_action)
    self._add_menu_action(workspace_menu, "Zoom", self.plot_zoom_action)
    workspace_menu.addSeparator()
    self._add_menu_action(workspace_menu, "X grid", self.plot_x_grid_action)
    self._add_menu_action(workspace_menu, "Y grid", self.plot_y_grid_action)

    if self.plot_options_menu is not None:
        workspace_menu.addSeparator()
        self._add_proxy_menu(
            workspace_menu,
            "Plot options",
            self.plot_options_menu,
        )
    if self.plot_view_menu is not None:
        self._add_proxy_menu(
            workspace_menu,
            "ViewBox options",
            self.plot_view_menu,
        )

    workspace_menu.addSeparator()

    workspace_menu.addAction("System summary", lambda: self.system.summary(table=True))
    workspace_menu.addAction(
        "Workspace summary", lambda: self.workspace_inspector.summary(table=True)
    )
    workspace_menu.addSeparator()
    workspace_menu.addAction("System help", lambda: self.system.help(table=True))
    workspace_menu.addAction(
        "Workspace help", lambda: self.workspace_inspector.help(table=True)
    )

    analysis_menu = menu_bar.addMenu("&Analysis")
    analysis_menu.addAction(self.toolbar_lyapunov_action)
    analysis_menu.addAction(self.toolbar_projection_action)
    analysis_menu.addAction(self.toolbar_poincare_action)
    analysis_menu.addAction(self.toolbar_bifurcation_action)
    analysis_menu.addAction(self.toolbar_jupyter_console_action)

    self._hide_menu_icons(file_menu)
    self._hide_menu_icons(view_menu)
    self._hide_menu_icons(system_menu)
    self._hide_menu_icons(workspace_menu)
    self._hide_menu_icons(analysis_menu)
    self._sync_menu_actions()


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
