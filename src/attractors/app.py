# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .colour import colourmap
from .console import analysis
from .console.jupyter_console_panel import JupyterConsolePanel
from .console.live_plot_controller import LivePlotController
from .console.system import SystemCommands, SystemInspector, SystemSettings
from .console.workspace_controller import WorkspaceController
from .console.workspace_inspector import WorkspaceInspector
from .perf import PerfProfiler, perf_finish, perf_start, profiling_enabled
from .presets import (
    PresetError,
    delete_named_preset,
    list_presets,
    load_named_preset,
    preset_metadata,
    save_named_preset,
)
from .systems.registry import ATTRACTORS
from .ui import session_store
from .ui.bifurcation_panel import BifurcationPanel
from .ui.control_panel import ControlPanel
from .ui.docking import DockLayout
from .ui.lyapunov_panel import LyapunovPanel
from .ui.main_toolbar import MainToolbar
from .ui.menu_bar import MainMenuBar
from .ui.output_panel import OutputPanel
from .ui.phase_panel import PhasePortraitPanel
from .ui.poincare_panel import PoincarePanel
from .ui.projection_panel import ProjectionPanel
from .ui.right_panel import RightPanel
from .ui.signal_panel import SignalPanel
from .ui.startup import WelcomeDialog
from .ui.status_bar import AppStatusBar
from .ui.style import MAIN_WINDOW, plot_colours
from .ui.system_toolbar import SystemToolbar
from .ui.trajectory_analysis_panel import TrajectoryAnalysisPanel
from .ui.workspace_toolbar import WorkspaceToolbar
from .view.view_manager import ViewManager
from .workers.solve_manager import SolveManager
from .workers.solve_session import SolveSession

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PROJECTION_UPDATE_INTERVAL = 100  # ms


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Systems analysis")
        self.setStyleSheet(MAIN_WINDOW)
        self.setContentsMargins(5, 0, 5, 0)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.dock_layout = DockLayout(self)

        self.reset_session_state = False

        self._restoring_view = False
        self._active_lyapunov_request_id = None
        self._lyapunov_perf_tokens = {}
        self._last_projection_update = None
        self._perf = PerfProfiler()
        self._panel_docks = {}
        self._open_analysis_panels = set()
        self.workspace_mode = "system"

        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = next(iter(ATTRACTORS.keys()))
        self._custom_config = None

        app_data_location = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.AppDataLocation
        )
        if app_data_location:
            self._preset_directory = app_data_location + "/presets"
            self._app_data_directory = Path(app_data_location)
        else:
            self._preset_directory = (
                QtCore.QDir.homePath() + "/.strange-attractors/presets"
            )
            self._app_data_directory = Path(
                QtCore.QDir.homePath() + "/.strange-attractors"
            )
        self._scripts_directory = self._app_data_directory / "scripts"
        self._scripts_directory.mkdir(parents=True, exist_ok=True)

        self.solver = SolveManager(self)
        self.solve_session = SolveSession(self.solver, self)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)
        self.solver.lyapunov_failed.connect(self._on_lyapunov_failed)

        self.scene = ViewManager(self)
        self.scene.animation_segments_data.connect(
            lambda segments: self.live_plot_controller.refresh_preview(
                segments, kinds={"projection"}
            )
        )
        self.scene.projections_data.connect(self._on_projections_data)

        self.phase_portrait = PhasePortraitPanel()
        self.phase_portrait.field_update_requested.connect(self._update_phase_field)
        self.phase_portrait.seed_requested.connect(self._on_phase_seed)
        self.system_view = QtWidgets.QStackedWidget()
        self.system_view.addWidget(self.scene.container)
        self.system_view.addWidget(self.phase_portrait)
        self.system_view.setCurrentWidget(self.scene.container)

        self.controls = ControlPanel(self)
        self.right_panel = RightPanel(self.dock_layout)
        self.controls.set_right_panel(self.right_panel)
        self.controls.attractor_changed.connect(self.on_attractor_change)
        self.controls.solve_requested.connect(self._solve)
        self.controls.n_changed.connect(self._on_n_changed)
        self.controls.t_max_changed.connect(
            lambda val: setattr(self, "current_t_max", val)
        )
        self.controls.animation_speed_changed.connect(
            self.scene.animation_controller.set_step
        )
        self.controls.particle_count_changed.connect(self.scene.set_particle_count)
        self.controls.particle_trail_length_changed.connect(
            self.scene.set_particle_trail_length
        )
        self.controls.particle_size_changed.connect(
            self.scene.particle_renderer.set_particle_size
        )
        self.controls.particle_trail_width_changed.connect(
            self.scene.particle_renderer.set_trail_width
        )
        self.controls.orbit_speed_changed.connect(
            self.scene.camera_controller.set_orbit_speed
        )
        self.controls.alpha_slider.valueChanged.connect(
            self.scene.trajectory_renderer.set_alpha
        )
        self.controls.alpha_spin.valueChanged.connect(
            self.scene.trajectory_renderer.set_alpha
        )
        self.controls.plot_size_spin.valueChanged.connect(
            self.scene.trajectory_renderer.set_plot_size
        )
        self.controls.plot_size_spin.valueChanged.connect(
            self.controls.trajectory_panel.set_plot_size
        )
        self.controls.head_size_spin.valueChanged.connect(
            self.scene.trajectory_renderer.set_head_size
        )
        self.controls.colour_mode_changed.connect(self.scene.set_colour_mode)
        self.controls.colourmap_changed.connect(self.scene.set_colourmap)
        self.right_panel.preset_panel.preset_save_requested.connect(self._save_preset)
        self.right_panel.preset_panel.preset_load_requested.connect(self._load_preset)
        self.right_panel.preset_panel.preset_delete_requested.connect(
            self._delete_preset
        )
        self.right_panel.preset_panel.preset_selected.connect(
            self._update_preset_summary
        )
        self.controls.traj_tail_length_changed.connect(
            self.scene.trajectory_renderer.set_traj_tail_length
        )
        self.controls.trajectory_panel.trajectories_changed.connect(
            self._on_trajectories_changed
        )
        self.controls.trajectory_panel.styles_changed.connect(
            self._on_trajectory_styles_changed
        )
        self.controls.custom_panel.compile_requested.connect(self._on_custom_compile)

        self.poincare_panel = PoincarePanel()
        self.poincare_panel.plane_changed.connect(self._on_poincare_plane_changed)

        self.lyapunov_panel = LyapunovPanel()
        self.lyapunov_panel.compute_requested.connect(self._request_lyapunov)
        self.lyapunov_panel.close_requested.connect(
            lambda: self._close_panel_dock("lyapunov_panel")
        )

        self.projection_panel = ProjectionPanel()
        self.projection_panel.close_requested.connect(
            lambda: self._close_panel_dock("projection_panel")
        )

        self.bifurcation_panel = BifurcationPanel()
        self.bifurcation_panel.close_requested.connect(
            lambda: self._close_panel_dock("bifurcation_panel")
        )

        self.signal_panel = SignalPanel()

        self.trajectory_analysis_panel = TrajectoryAnalysisPanel()

        self.output_panel = OutputPanel()
        self.output_panel.hide()

        self.jupyter_console_panel = JupyterConsolePanel(
            self.dock_layout,
            self._jupyter_console_namespace,
            script_dir=self._scripts_directory,
        )
        self.system_toolbar = SystemToolbar()
        self.system = SystemInspector(
            self._system_settings,
            self.solve_session,
            self.jupyter_console_panel,
            self.scene.camera_controller.get_camera_state,
            SystemCommands(
                self._apply_console_values,
                self._apply_console_time,
                lambda: self._solve(True),
            ),
        )
        self.live_plot_controller = LivePlotController(
            self.system, self.jupyter_console_panel.plots, self.system_toolbar, self
        )
        self.system.live = self.live_plot_controller
        self.main_toolbar = MainToolbar(self)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.main_toolbar)
        self.workspace_toolbar = WorkspaceToolbar(
            self.main_toolbar, self.system_toolbar, self.jupyter_console_panel
        )
        self.workspace_controller = WorkspaceController(
            self.jupyter_console_panel,
            self.workspace_toolbar,
            self.system_toolbar,
            self.live_plot_controller,
        )
        self.live_plot_controller.changed.connect(self.workspace_controller.sync_views)
        self.live_plot_controller.trace_failed.connect(
            lambda message: self.status_bar.set_app_message(message, error=True)
        )
        self.jupyter_console_panel.script_panel.status_changed.connect(
            lambda message: self.status_bar.set_temporary_app_message(message)
        )

        self.jupyter_console_panel.set_explore_status_callback(
            lambda message, error=False: self.status_bar.set_temporary_app_message(
                message, error=error
            )
        )
        self.system_toolbar.plot_requested.connect(
            self.live_plot_controller.on_plot_requested
        )
        self.system_toolbar.live_trace_remove_requested.connect(
            self.live_plot_controller.remove
        )
        self.system_toolbar.live_plot_clear_requested.connect(
            self.live_plot_controller.unfollow
        )
        self.jupyter_console_panel.plots.current_changed.connect(
            lambda _name: self.workspace_controller.sync_views()
        )
        self.jupyter_console_panel.views3d.views_changed.connect(
            self.workspace_controller.sync_views
        )
        self.jupyter_console_panel.active_view_changed.connect(
            self.workspace_controller.sync_views
        )
        self.jupyter_console_panel.views3d.current_changed.connect(
            lambda _name: self.workspace_controller.sync_views()
        )
        self.solve_session.state_changed.connect(self._on_solve_state)
        self.solve_session.run_accepted.connect(self._on_run_accepted)
        self.solve_session.failed.connect(self._on_solve_failed)
        self.workspace_controller.sync_views()

        self.viewport_dock = self.dock_layout.add(
            "viewport", "Viewport", self.system_view
        )
        self.parameters_dock = self.dock_layout.add(
            "parameters", "Parameters", self.controls.controls_scroll
        )
        self.view_options_dock = self.dock_layout.add(
            "view_options", "View options", self.controls.animation_scroll
        )
        self.data_dock = self.dock_layout.add("data", "Data", self.controls.data_view)
        self._left_docks = [
            self.parameters_dock,
            self.view_options_dock,
            self.data_dock,
        ]
        self._right_docks = [
            self.right_panel.trajectory_dock,
            self.right_panel.preset_dock,
            self.right_panel.custom_dock,
        ]
        for name, title, panel in (
            ("lyapunov_panel", "Lyapunov", self.lyapunov_panel),
            ("poincare_panel", "Poincare", self.poincare_panel),
            ("bifurcation_panel", "Bifurcation", self.bifurcation_panel),
            ("projection_panel", "Projection heatmaps", self.projection_panel),
            ("signal_panel", "Signal and spectrum", self.signal_panel),
            (
                "trajectory_analysis_panel",
                "Trajectory analysis",
                self.trajectory_analysis_panel,
            ),
        ):
            self._panel_docks[name] = self.dock_layout.add(
                f"analysis/{name}", title, panel
            )
        self.output_dock = self.dock_layout.add("output", "Output", self.output_panel)

        panel = self.trajectory_analysis_panel
        panel.play_requested.connect(self.scene.animation_controller.toggle)
        panel.seek_requested.connect(self.scene.seek_time)

        self.scene.playback_range_changed.connect(panel.set_playback_range)
        self.scene.playback_time_changed.connect(panel.set_playback_time)
        self.scene.animation_state_changed.connect(panel.set_playing)
        self.scene.animation_state_changed.connect(self.main_toolbar.set_playing)

        self.menu_bar = MainMenuBar(
            self.main_toolbar,
            self.dock_layout.menu,
            self._panel_docks["signal_panel"].toggleViewAction(),
            self._panel_docks["trajectory_analysis_panel"].toggleViewAction(),
            self.jupyter_console_panel.plot_widget.getPlotItem(),
            self.jupyter_console_panel.script_panel.example_scripts(),
        )
        self.setMenuBar(self.menu_bar)
        self._connect_main_actions()

        self.controls.animation_mode_changed.connect(self._set_animation_mode)
        self.status_bar = AppStatusBar(
            self.menu_bar.output_panel_action, self.menu_bar.status_bar_action
        )
        self.setStatusBar(self.status_bar)
        self.signal_panel.status_changed.connect(self.status_bar.set_signal_message)

        self.workspace_inspector = WorkspaceInspector(self.jupyter_console_panel)

        self._dock_state_timer = QtCore.QTimer(self)
        self._dock_state_timer.setSingleShot(True)
        self._dock_state_timer.timeout.connect(self._sync_dock_state)
        self.dock_layout.changed.connect(lambda: self._dock_state_timer.start(0))

        self.scene.container.installEventFilter(self)

        self.scene.grid_overlay.build_grid()
        self._refresh_presets()
        self.controls.set_current_attractor(self.current_name)
        self._rebuild_view(self.current_name)

        self._restore_app_layout()
        if profiling_enabled():
            self.menu_bar.output_panel_action.setChecked(True)

    def _connect_main_actions(self):
        toolbar = self.main_toolbar
        menu = self.menu_bar
        workspace = self.workspace_toolbar
        controller = self.workspace_controller
        scene = self.scene
        for signal, slot in (
            (toolbar.left_panel_action.toggled, self._set_left_panel_visible),
            (toolbar.right_panel_action.toggled, self._set_right_panel_visible),
            (toolbar.anim_action.triggered, scene.animation_controller.toggle),
            (toolbar.loop_action.toggled, scene.animation_controller.set_loop),
            (toolbar.reset_action.triggered, self.controls.reset_to_defaults),
            (toolbar.reset_camera_action.triggered, self._reset_camera),
            (toolbar.fit_camera_action.triggered, self._fit_camera),
            (
                toolbar.save_view_action.triggered,
                scene.viewport_overlay.save_view_as_png,
            ),
            (toolbar.point_action.toggled, scene.trajectory_renderer.set_point_mode),
            (toolbar.point_action.toggled, self.controls.head_size_wrapper.setVisible),
            (toolbar.line_action.toggled, self._set_line_mode),
            (toolbar.trail_action.toggled, self._set_trail_mode),
            (toolbar.grid_action.toggled, scene.grid_overlay.set_grid_visible),
            (toolbar.orbit_action.toggled, self._set_orbit_mode),
            (toolbar.hover_action.toggled, scene.point_hover.set_enabled),
            (toolbar.solve_action.triggered, lambda: self._solve(True)),
            (toolbar.system_action.triggered, self._toggle_system_workspace),
            (
                toolbar.explore_action.triggered,
                lambda: self._set_workspace_mode("explore"),
            ),
            (menu.output_panel_action.toggled, self.output_dock.setVisible),
            (
                menu.save_view_action.triggered,
                scene.viewport_overlay.save_view_as_png,
            ),
            (menu.open_preset_folder_action.triggered, self._open_preset_folder),
            (menu.welcome_action.triggered, self.show_welcome),
            (menu.help_action.triggered, self.help),
            (menu.reset_layout_action.triggered, self._restore_default_layout),
            (menu.reset_camera_action.triggered, self._reset_camera),
            (menu.fit_view_action.triggered, self._fit_camera),
            (menu.reset_session_action.triggered, self._reset_session_state),
            (menu.solve_action.triggered, lambda: self._solve(True)),
            (menu.reset_parameters_action.triggered, self.controls.reset_to_defaults),
            (menu.summary_action.triggered, self.show_workspace_summary),
            (
                menu.explore_workspace_action.triggered,
                lambda: self._set_workspace_mode("explore"),
            ),
            (
                menu.examples_menu.triggered,
                lambda action: self._open_example_script(action.data()),
            ),
            (menu.new_plot_action.triggered, controller.new_plot),
            (menu.clear_view_action.triggered, controller.clear_current_view),
            (menu.export_table_action.triggered, self._export_current_table),
            (menu.clear_all_views_action.triggered, controller.clear_all_views),
            (menu.clear_sliders_action.triggered, controller.clear_explore_sliders),
            (menu.clear_traces_action.triggered, controller.clear_explore_traces),
            (menu.clear_explore_action.triggered, controller.clear_explore),
            (
                menu.system_summary_action.triggered,
                lambda: self.system.summary(table=True),
            ),
            (
                menu.workspace_summary_action.triggered,
                lambda: self.workspace_inspector.summary(table=True),
            ),
            (menu.system_help_action.triggered, lambda: self.system.help(table=True)),
            (
                menu.workspace_help_action.triggered,
                lambda: self.workspace_inspector.help(table=True),
            ),
            (
                workspace.view_combo.currentIndexChanged,
                lambda _index: controller.on_toolbar_view_selected(),
            ),
            (workspace.name_edit.returnPressed, self._rename_current_view),
            (workspace.new_plot_action.triggered, controller.new_plot),
            (workspace.new_view3d_action.triggered, controller.new_view3d),
            (workspace.rename_action.triggered, self._rename_current_view),
            (workspace.clear_view_action.triggered, controller.clear_current_view),
            (workspace.clear_all_action.triggered, controller.clear_all_views),
            (workspace.fit_action.triggered, controller.fit_current_view),
            (workspace.reset_action.triggered, controller.reset_current_view),
            (workspace.grid_action.toggled, controller.set_current_grid_visible),
            (workspace.orbit_action.toggled, controller.set_current_view_orbit),
            (
                workspace.crosshair_action.toggled,
                controller.set_current_crosshair_visible,
            ),
            (
                workspace.trace_menu.triggered,
                lambda action: controller.remove_explore_trace(action.data()),
            ),
            (
                workspace.clear_sliders_action.triggered,
                controller.clear_explore_sliders,
            ),
            (workspace.clear_explore_action.triggered, controller.clear_explore),
        ):
            signal.connect(slot)
        self.controls.head_size_wrapper.setVisible(toolbar.point_action.isChecked())

        for actions, slot in (
            (menu.theme_actions, self._set_theme),
            (menu.animation_mode_actions, self._set_animation_mode),
            (menu.workspace_mode_actions, self._set_workspace_mode),
            (menu.panel_actions, self._toggle_panel_dock),
        ):
            for value, action in actions.items():
                action.triggered.connect(
                    lambda _checked=False, slot=slot, value=value: slot(value)
                )

    def _on_poincare_plane_changed(self, axis, value):
        self.scene.grid_overlay.remove_poincare_plane()
        self.phase_portrait.set_section()

        config, _values = self._get_current_config_and_values()
        if (
            config is None
            or axis not in config.variables
            or not self._panel_visible("poincare_panel")
        ):
            return

        if config.dimension == 2:
            self.phase_portrait.set_section(axis, value)
        else:
            self.scene.grid_overlay.set_poincare_plane(axis, value)

    def _on_phase_seed(self, x, y):
        config, _values = self._get_current_config_and_values()
        if config is None or config.dimension != 2:
            return

        try:
            added = self.controls.trajectory_panel.add_initial_condition([x, y])
        except ValueError as e:
            self.status_bar.set_app_message(str(e), error=True)
            return

        if not added:
            self.status_bar.set_app_message("Trajectory limit reached", error=True)

    def _update_phase_field(self):
        panel = self.phase_portrait
        config, _values = self._get_current_config_and_values()

        if (
            config is None
            or config.dimension != 2
            or not panel.field_check.isChecked()
            or self.system_view.currentWidget() is not panel
        ):
            return

        x_range, y_range = panel.view_box.viewRange()

        try:
            frame = self.system.vector_field_slice(
                x_range=x_range, y_range=y_range, density=21
            )
            x, y = self.system._vector_field_segments(frame, "x", "y", scale=0.75)
        except (ValueError, ArithmeticError) as e:
            panel.field_item.clear()
            self.status_bar.set_app_message(str(e), error=True)
            return

        panel.set_vector_field(x, y)

    def on_attractor_change(self, name):
        self.current_name = name
        self._rebuild_view(name)

    def _rebuild_view(self, name):
        if name == "Custom":
            self._rebuild_view_custom()
            return
        self._rebuild_view_from_config(ATTRACTORS[name])

    def _rebuild_view_custom(self):
        self.scene.animation_controller.stop()
        self.controls.hide_standard_controls()

        if self._custom_config is not None:
            self._apply_config_to_view(self._custom_config)
        else:
            self.solve_session.clear()
            self.solver.cancel_lyapunov()
            self.scene.clear_solutions()
            self.controls.data_view.clear()
            self.lyapunov_panel.clear()
            self.phase_portrait.clear()

    def _rebuild_view_from_config(self, config):
        self.scene.animation_controller.stop()
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self.solve_session.clear()
        self._restoring_view = True
        try:
            self.phase_portrait.clear()
            self.scene.clear_solutions()
            self._select_system_view(config)
            self._configure_system_capabilities(config)
            self.scene.viewport_overlay.set_info(
                config,
                self.controls.get_current_values(),
            )
            self.scene.camera_controller.set_camera(config)
            self.controls.configure(config)
            self.current_n = config.time_defaults.n
            self.current_t_max = config.time_defaults.t_max
            self.controls.set_traj_tail_max(self.current_n)
            self.lyapunov_panel.clear()
            self.controls.trajectory_panel.reset(config)
            self.bifurcation_panel.set_config(
                config, self.controls.get_current_values()
            )
        finally:
            self._restoring_view = False
        self._update_plot()

    def _on_custom_compile(self, config):
        self._custom_config = config
        self.current_name = "Custom"
        self.controls.set_current_attractor("Custom")
        self._apply_config_to_view(config)

    def _apply_loaded_preset(self, config, values, n, t_max):
        self.solve_session.clear()
        self._restoring_view = True
        try:
            self.phase_portrait.clear()
            self.scene.clear_solutions()
            self._select_system_view(config)
            self._configure_system_capabilities(config)
            if config.name == "Custom":
                self._custom_config = config
                self.current_name = "Custom"
                self.controls.set_current_attractor("Custom")
                self.controls.hide_standard_controls()
            else:
                name = next(
                    (name for name, con in ATTRACTORS.items() if con is config),
                    config.name,
                )
                self.current_name = name
                self.controls.set_current_attractor(name)
                self.controls.show_standard_controls()

            self.scene.animation_controller.stop()
            self.scene.camera_controller.set_camera(config)
            self.controls.configure(config)

            if config.name == "Custom":
                self.controls.custom_panel.set_from_config(config)

            self.controls.set_current_values(values)
            self.controls.set_time_values(n, t_max)
            self.current_n = n
            self.current_t_max = t_max
            self.controls.set_traj_tail_max(self.current_n)
            self.scene.viewport_overlay.set_info(
                config,
                self.controls.get_current_values(),
            )
            self.lyapunov_panel.clear()
            self.controls.trajectory_panel.reset(config)
            self.bifurcation_panel.set_config(
                config, self.controls.get_current_values()
            )
        finally:
            self._restoring_view = False
        self._update_plot()

    def _refresh_presets(self, selected=None):
        preset_panel = self.controls.preset_panel
        preset_panel.set_saved_presets(list_presets(self._preset_directory), selected)
        self._update_preset_summary(selected or preset_panel.current_preset_name())

    def _set_workspace_mode(self, mode):
        if mode not in {"system", "explore"}:
            raise ValueError("Workspace mode must be 'system' or 'explore'")
        self.workspace_mode = mode
        self.dock_layout.switch(mode)
        self.jupyter_console_panel.set_explore_visible(mode == "explore")
        self._sync_dock_state()
        self.menu_bar.workspace_mode_actions[mode].setChecked(True)

    def _toggle_system_workspace(self):
        if self.workspace_mode != "system":
            self._set_workspace_mode("system")
            if self._workspace_visible():
                return
        elif self._workspace_visible():
            side_docks = [self.parameters_dock, self.right_panel.trajectory_dock]
            widths = [dock.width() for dock in side_docks]
            for dock in self.jupyter_console_panel.docks():
                dock.hide()
            self.resizeDocks(
                [side_docks[0], self.viewport_dock, side_docks[1]],
                [widths[0], max(self.width() - sum(widths), 1), widths[1]],
                QtCore.Qt.Orientation.Horizontal,
            )
            self._sync_dock_state()
            return

        panel = self.jupyter_console_panel
        panel.plot_dock.show()
        panel.script_dock.show()
        panel.files_dock.show()
        panel.variables_dock.show()
        panel.console_dock.show()
        panel.plot_dock.raise_()
        panel.console_dock.raise_()
        self.dock_layout.resize_defaults()
        self._sync_dock_state()

    def _restore_default_layout(self):
        self.dock_layout.reset()
        self._sync_dock_state()
        self.status_bar.set_temporary_app_message(
            f"Restored {self.workspace_mode.title()} layout"
        )

    def _set_theme(self, theme):
        QtWidgets.QApplication.instance().setProperty("appTheme", theme)
        self.menu_bar.theme_actions[theme].setChecked(True)
        self._apply_theme()

    def _apply_theme(self):
        colours = plot_colours()
        self.controls.plot_size_spin.setValue(colours["scatter_size"])
        self.controls.trajectory_panel.set_plot_size(colours["scatter_size"])

        self.scene.view.setBackgroundColor(colours["gl_background"])
        self.scene.grid_overlay.apply_theme()
        self.scene.trajectory_renderer.apply_theme()
        self.scene.particle_renderer.apply_theme()

        self.scene.viewport_overlay.apply_theme()

        self.lyapunov_panel.apply_theme()
        self.poincare_panel.apply_theme()
        self.bifurcation_panel.apply_theme()
        self.projection_panel.apply_theme()
        self.signal_panel.apply_theme()
        self.jupyter_console_panel.apply_theme()
        self.phase_portrait.apply_theme()
        self.trajectory_analysis_panel.apply_theme()

    def _set_left_panel_visible(self, checked):
        for dock in self._left_docks:
            dock.setVisible(checked)

    def _set_trail_mode(self, checked):
        self.scene.trajectory_renderer.set_trail_mode(checked)
        self.controls.set_trail_options_visible(checked)

    def _set_animation_mode(self, mode):
        if mode == self.scene.animation_mode:
            return

        self.scene.set_animation_mode(mode)
        with QtCore.QSignalBlocker(self.controls.animation_mode_combo):
            index = self.controls.animation_mode_combo.findData(mode)
            if index >= 0:
                self.controls.animation_mode_combo.setCurrentIndex(index)

        particle_flow = mode == "particle"

        self.controls.set_particle_options_visible(particle_flow)
        self.main_toolbar.loop_action.setEnabled(not particle_flow)
        self.main_toolbar.point_action.setEnabled(not particle_flow)
        self.menu_bar.animation_mode_actions[mode].setChecked(True)

    def _set_line_mode(self, checked):
        mode = "line" if checked else "points"
        self.controls.trajectory_panel.set_render_mode_all(mode)
        self.scene.trajectory_renderer.set_line_mode(checked)
        # self.controls.set_linewidth_option_visible(checked)

    def _set_orbit_mode(self, enabled):
        self.scene.camera_controller.set_orbit_mode(enabled)
        self.controls.orbit_speed_wrapper.setVisible(enabled)

    def _set_right_panel_visible(self, checked):
        for dock in self._right_docks:
            dock.setVisible(checked)

    def _open_example_script(self, path):
        if self.jupyter_console_panel.script_panel.load_script(path):
            self._set_workspace_mode("explore")
            self.status_bar.set_temporary_app_message(f"Opened example: {path.name}")

    def _open_preset_folder(self):
        Path(self._preset_directory).mkdir(parents=True, exist_ok=True)
        opened = QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(self._preset_directory)
        )
        if not opened:
            self.status_bar.set_app_message("Could not open preset folder", error=True)

    def _update_preset_summary(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.controls.preset_panel.set_preset_notes("")
            self.controls.preset_panel.set_preset_summary("No saved presets")
            return

        try:
            metadata = preset_metadata(self._preset_directory, preset_name)
        except PresetError as exc:
            self.controls.preset_panel.set_preset_notes("")
            self.controls.preset_panel.set_preset_summary(str(exc))
            return

        kind = "custom" if metadata["is_custom"] else "built-in"
        summary = (
            f"{metadata['attractor']} ({kind}) · "
            f"N {metadata['n']} · t_max {metadata['t_max']} · "
            f"{metadata['parameter_count']} parameter(s)"
        )
        updated_at = metadata.get("updated_at")
        if updated_at:
            summary = f"{summary}\nUpdated {updated_at}"
        self.controls.preset_panel.set_preset_notes(metadata["notes"])
        self.controls.preset_panel.set_preset_summary(summary)

    def _save_preset(self, name, notes):
        config, values = self._get_current_config_and_values()
        if config is None:
            self.status_bar.set_app_message("No attractor selected", error=True)
            return

        preset_name = name.strip() or f"{self.current_name} preset"

        try:
            save_named_preset(
                self._preset_directory,
                preset_name,
                config,
                values,
                self.current_n,
                self.current_t_max,
                notes,
            )
        except PresetError as exc:
            self.status_bar.set_app_message(str(exc), error=True)
            return

        self._refresh_presets(preset_name)
        self.status_bar.set_app_message(f"Saved preset: {preset_name}")

    def _load_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.status_bar.set_app_message("Select a preset to load", error=True)
            return

        try:
            config, values, n, t_max = load_named_preset(
                self._preset_directory, preset_name
            )
        except PresetError as exc:
            self.status_bar.set_app_message(str(exc), error=True)
            return

        self._apply_loaded_preset(config, values, n, t_max)
        self._refresh_presets(preset_name)
        self.status_bar.set_app_message(f"Loaded preset: {preset_name}")

    def _delete_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.status_bar.set_app_message("Select a preset to delete", error=True)
            return

        try:
            delete_named_preset(self._preset_directory, preset_name)
        except PresetError as exc:
            self.status_bar.set_app_message(str(exc), error=True)
            return

        self._refresh_presets()
        self.status_bar.set_app_message(f"Deleted preset: {preset_name}")

    def _get_current_config_and_values(self):
        if self.current_name == "Custom":
            config = self._custom_config
        else:
            config = ATTRACTORS[self.current_name]
        if config is None:
            return None, {}
        values = self.controls.get_current_values()
        return config, values

    def _jupyter_console_namespace(self):
        plot = self.jupyter_console_panel.plot
        return {
            "np": np,
            "pd": pd,
            "pg": pg,
            "colourmap": colourmap,
            "system": self.system,
            "plot": plot,
            "plots": self.jupyter_console_panel.plots,
            "current_plot": lambda: self.jupyter_console_panel.plots.current,
            "view3d": self.jupyter_console_panel.view3d,
            "views3d": self.jupyter_console_panel.views3d,
            "current_view3d": lambda: self.jupyter_console_panel.views3d.current,
            "tables": self.jupyter_console_panel.tables,
            "table": self.jupyter_console_panel.table,
            "current_table": lambda: self.jupyter_console_panel.tables.current,
            "current_values": lambda: self.system.values,
            "scripts_dir": self._scripts_directory,
            "workspace": self.workspace_inspector,
            "analysis": analysis,
        }

    def _system_settings(self):
        config, values = self._get_current_config_and_values()
        return SystemSettings(
            self.current_name,
            config,
            values,
            self.current_n,
            self.current_t_max,
            self.controls.trajectory_panel.get_trajectories(),
        )

    def _apply_console_values(self, values):
        config, _values = self._get_current_config_and_values()
        self.controls.set_current_values(values)
        self.scene.viewport_overlay.set_info(config, self.controls.get_current_values())

    def _apply_console_time(self, n, t_max):
        self.current_n = n
        self.current_t_max = t_max
        self.controls.set_time_values(n, t_max)
        self.controls.set_traj_tail_max(n)

    def _on_solve_state(self, state):
        run = self.solve_session.analysis_run
        self.signal_panel.set_source(run, state)
        self.trajectory_analysis_panel.set_source(run, state)

        playable = (
            run is not None
            and state["valid"]
            and not state["stale"]
            and not state["solving"]
            and state["request_id"] == run.request_id
            and len(run.variables) == 3
        )
        self.scene.set_playback_source(run if playable else None)
        self.main_toolbar.anim_action.setEnabled(playable)

        if state["solving"] and not state["partial"]:
            count = state["trajectories"]
            self.status_bar.set_app_message(
                "Solving trajectory" if count == 1 else f"Solving {count} trajectories"
            )

    def _update_plot(self):
        self._solve(True)
        config, values = self._get_current_config_and_values()
        if config is not None:
            self.scene.viewport_overlay.set_info(config, values)

    def _solve(self, full):
        self.scene.animation_controller.stop()
        self.solver.cancel_lyapunov()
        settings = self._system_settings()
        self.solve_session.solve(
            full,
            settings.config,
            settings.values,
            settings.n,
            settings.t_max,
            settings.trajectories,
            record=self._panel_visible("signal_panel")
            or self._panel_visible("trajectory_analysis_panel"),
        )

    def _request_lyapunov(self):
        if not self._panel_visible("lyapunov_panel"):
            return

        config, values = self._get_current_config_and_values()
        if config is None:
            self.status_bar.set_app_message("No attractor selected", error=True)
            return

        self.solver.cancel_lyapunov()
        self.status_bar.set_app_message("Computing Lyapunov spectrum")
        self._active_lyapunov_request_id = self.solver.request_lyapunov(
            config,
            values,
            self.current_n,
            self.current_t_max,
        )
        token = perf_start(
            self,
            "lyapunov",
            key=self._active_lyapunov_request_id,
            attractor=config.name,
            n=self.current_n,
            t_max=self.current_t_max,
        )
        if token is not None:
            self._lyapunov_perf_tokens[self._active_lyapunov_request_id] = token

    def _on_run_accepted(self, run):
        solutions = run.solutions
        self.status_bar.clear_app_message()
        self._display_system_solution(run)
        self._update_projection_panel_from_solutions(solutions)
        if run.partial:
            self.live_plot_controller.refresh_preview(solutions)
            return

        self.controls.data_view.set_solutions(
            solutions,
            t_min=run.t_min,
            trajectory_specs=run.trajectory_specs,
            config=run.config,
            values=run.parameters,
        )
        if run.config.dimension == 3:
            self.scene.grid_overlay.auto_adjust_grid(solutions)

        if self.lyapunov_panel.auto_enabled():
            self._request_lyapunov()
        if self._panel_visible("poincare_panel"):
            self.poincare_panel.set_attractor(run.config, run.parameters)
        self.bifurcation_panel.current_values = dict(run.parameters)
        self.live_plot_controller.refresh_all()

    def _on_solve_failed(self, message, partial):
        if not partial:
            self.controls.data_view.clear()
        self.status_bar.set_app_message(message, error=True)

    def _configure_system_capabilities(self, config):
        self.system_toolbar.set_variables(config.variables)
        is_3d = config.dimension == 3

        self.lyapunov_panel.setEnabled(True)
        self.poincare_panel.setEnabled(True)
        self.controls.animation_scroll.setEnabled(is_3d)

        for panel in (
            self.lyapunov_panel,
            self.poincare_panel,
            self.projection_panel,
            self.bifurcation_panel,
        ):
            panel.setEnabled(True)
            panel.setToolTip("")

        self._cancel_lyapunov_analysis()
        self.lyapunov_panel.clear()
        self.poincare_panel.clear()
        self.projection_panel.clear()
        self.phase_portrait.set_section()
        self.scene.grid_overlay.remove_poincare_plane()

        for action in (
            *self.main_toolbar.scene_actions,
            *self.menu_bar.animation_mode_actions.values(),
        ):
            action.setEnabled(is_3d)

        if not is_3d:
            self.scene.animation_controller.stop()
            self.scene.camera_controller.set_orbit_mode(False)

        self._cancel_lyapunov_analysis()
        self.lyapunov_panel.clear()
        self.poincare_panel.clear()
        self.projection_panel.clear()

    def _select_system_view(self, config):
        widget = self.phase_portrait if config.dimension == 2 else self.scene.container
        self.system_view.setCurrentWidget(widget)

    def _display_system_solution(self, run):
        solutions = run.solutions
        self._select_system_view(run.config)

        if run.config.dimension == 2:
            self.phase_portrait.set_trajectories(
                self.controls.trajectory_panel.get_trajectories()
            )
            self.phase_portrait.display_solutions(
                solutions, initial_conditions=run.initial_conditions
            )
            self.phase_portrait.request_field_update()
            return

        self.scene.trajectory_renderer.set_time_steps(
            [(spec["t_max"] - run.t_min) / spec["n"] for spec in run.trajectory_specs]
        )
        self.scene.display_solutions(solutions, run.partial)

        if self.main_toolbar.auto_fit_camera_action.isChecked():
            self.scene.camera_controller.fit_camera_to_solutions(solutions)
            self.scene.grid_overlay.auto_adjust_grid(solutions)

    def _update_projection_panel_from_solutions(self, solutions):
        if not self._panel_visible("projection_panel"):
            return

        all_sol = np.concatenate(solutions, axis=0)
        token = perf_start(
            self,
            "projection_update",
            source="solve_result",
            points=len(all_sol),
        )
        self.projection_panel.update_projections(*all_sol.T)
        perf_finish(self, token)
        self._last_projection_update = QtCore.QDateTime.currentMSecsSinceEpoch()

    def _on_projections_data(self, x, y, z):
        if not self._panel_visible("projection_panel"):
            return

        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        if (
            self._last_projection_update is not None
            and now_ms - self._last_projection_update < PROJECTION_UPDATE_INTERVAL
        ):
            return

        self._last_projection_update = now_ms
        token = perf_start(
            self,
            "projection_update",
            source="animation",
            points=len(x),
        )
        self.projection_panel.update_projections(x, y, z)
        perf_finish(self, token)

    def _reset_camera(self):
        config, _ = self._get_current_config_and_values()
        if config is not None:
            self.scene.camera_controller.set_camera(config)

    def _fit_camera(self):
        self.scene.camera_controller.fit_camera_to_solutions(
            self.scene.trajectory_renderer.solutions
        )

    def _on_n_changed(self, val):
        self.current_n = val
        self.controls.set_traj_tail_max(val)

    def _on_trajectories_changed(self, trajectories):
        self.scene.trajectory_renderer.set_trajectories(trajectories)
        if self._restoring_view:
            return

        self.solve_session.clear()

        config, _values = self._get_current_config_and_values()
        if config is None or config.dimension == 3:
            self.scene.clear_solutions()

        self.controls.data_view.clear()
        self._solve(True)

    def _on_trajectory_styles_changed(self, trajectories):
        config, _values = self._get_current_config_and_values()

        if config is not None and config.dimension == 2:
            self.phase_portrait.set_trajectories(trajectories)
            return

        renderer = self.scene.trajectory_renderer
        renderer.set_trajectories(trajectories)
        renderer.update_display()

    def _on_lyapunov_result(self, request_id, lyap, ky_dim, t_hist, lyap_hist):
        if request_id != self._active_lyapunov_request_id:
            return
        if not self._panel_visible("lyapunov_panel"):
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token)
        self.lyapunov_panel.set_result(lyap, ky_dim, t_hist, lyap_hist)
        self.status_bar.clear_app_message()

    def _on_lyapunov_failed(self, request_id, message):
        if request_id != self._active_lyapunov_request_id:
            return
        if not self._panel_visible("lyapunov_panel"):
            self._cancel_lyapunov_analysis()
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token, status="failed")
        self.status_bar.set_app_message(f"Lyapunov failed: {message}", error=True)

    def _panel_visible(self, panel_name):
        return not self._panel_docks[panel_name].isHidden()

    def _workspace_visible(self):
        return any(not dock.isHidden() for dock in self.jupyter_console_panel.docks())

    def _open_panel_dock(self, panel_name):
        self._panel_docks[panel_name].reveal()
        self._sync_dock_state()

    def _close_panel_dock(self, panel_name):
        self._panel_docks[panel_name].hide()
        self._sync_dock_state()

    def _toggle_panel_dock(self, panel_name):
        if self._panel_visible(panel_name):
            self._close_panel_dock(panel_name)
        else:
            self._open_panel_dock(panel_name)

    def _sync_dock_state(self):
        opened = {
            name for name, dock in self._panel_docks.items() if not dock.isHidden()
        }
        previous = self._open_analysis_panels
        self._open_analysis_panels = opened
        for name in previous - opened:
            if name == "lyapunov_panel":
                self._cancel_lyapunov_analysis()
            elif name == "poincare_panel":
                self.poincare_panel.cancel_solve()
                self.scene.grid_overlay.remove_poincare_plane()
            elif name == "bifurcation_panel":
                self.bifurcation_panel.cancel_sweep()
        for name in opened - previous:
            config, _values = self._get_current_config_and_values()
            if config is None:
                continue

            if name == "lyapunov_panel" and self.lyapunov_panel.auto_enabled():
                self._request_lyapunov()
            elif name == "projection_panel":
                run = self.solve_session.run
                self.projection_panel.reapply_projections(run.solutions if run else [])
            elif name == "poincare_panel":
                config, values = self._get_current_config_and_values()
                self.poincare_panel.set_attractor(config, values)
                self.poincare_panel.recompute()
            elif name == "bifurcation_panel":
                config, values = self._get_current_config_and_values()
                if config is not None:
                    self.bifurcation_panel.set_config(config, values)
            elif name == "trajectory_analysis_panel" and (
                self.solve_session.analysis_run is None
                or self.solve_session.state["partial"]
            ):
                self._solve(True)
        toolbar = self.main_toolbar
        for action, checked in (
            (
                toolbar.left_panel_action,
                any(not dock.isHidden() for dock in self._left_docks),
            ),
            (
                toolbar.right_panel_action,
                any(not dock.isHidden() for dock in self._right_docks),
            ),
            (
                toolbar.system_action,
                self.workspace_mode == "system" and self._workspace_visible(),
            ),
            (toolbar.explore_action, self.workspace_mode == "explore"),
            (self.menu_bar.output_panel_action, not self.output_dock.isHidden()),
            *(
                (action, name in opened)
                for name, action in self.menu_bar.panel_actions.items()
            ),
        ):
            with QtCore.QSignalBlocker(action):
                action.setChecked(checked)

        system_mode = self.workspace_mode == "system"
        for action in toolbar.viewport_actions:
            action.setVisible(system_mode)
        self.workspace_toolbar.set_workspace_state(
            self.workspace_mode, self._workspace_visible()
        )

    def _cancel_lyapunov_analysis(self):
        self.solver.cancel_lyapunov()

        request_id = self._active_lyapunov_request_id
        if request_id is not None:
            token = self._lyapunov_perf_tokens.pop(request_id, None)
            perf_finish(self, token, status="cancelled")
        self._active_lyapunov_request_id = None
        self.status_bar.clear_app_message()

    def _workspace_summary(self):
        plots = self.jupyter_console_panel.plots
        current_plot = plots.current
        plot_names = plots.names()
        slider_names = current_plot.explore.slider_names()
        trace_names = current_plot.explore.trace_names()

        return "\n".join(
            [
                f"Plots: {', '.join(plot_names)}",
                f"Current view: {plots.current_name}",
                f"Sliders: {', '.join(slider_names)}",
                f"Traces: {', '.join(trace_names)}",
            ]
        )

    def show_workspace_summary(self):
        QtWidgets.QMessageBox.information(
            self,
            "Jupyter Workspace Summary",
            self._workspace_summary(),
        )

    def _export_current_table(self):
        name = self.jupyter_console_panel.tables.current_name
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export current table", f"{name}.csv", "CSV (*.csv)"
        )

        if not path:
            return

        try:
            target = self.jupyter_console_panel.tables.export(
                path, name=name, index=False
            )
        except OSError as e:
            self.status_bar.set_app_message(f"Failed to export table: {e}", error=True)
            return

        self.status_bar.set_app_message(f"Exported table to {target}")

    def show_welcome(self):
        dialog = WelcomeDialog(self, session_store.app_settings())
        dialog.system_requested.connect(lambda: self._set_workspace_mode("system"))
        dialog.example_requested.connect(self._open_welcome_example)
        dialog.help_requested.connect(self.help)
        dialog.exec()

    def _open_welcome_example(self):
        scripts = self.jupyter_console_panel.script_panel.example_scripts()
        if scripts:
            self._open_example_script(scripts[0])
        else:
            self._set_workspace_mode("explore")
            self.status_bar.set_temporary_app_message("No bundled examples available")

    def help(self):
        QtWidgets.QMessageBox.information(
            self,
            "Systems analysis",
            "<p><b>Getting started</b><br>"
            "Choose a built-in system or enter equations in the Custom panel. "
            "Adjust parameters and initial conditions, then select "
            "System → Solve. Use the toolbar to play the animation.</p>"
            "<p><b>Analysis</b><br>"
            "Open the Analysis menu for signal and spectrum analysis, "
            "Lyapunov exponents, projections, Poincaré sections "
            "and bifurcation diagrams.</p>"
            "<p><b>Panels and layout</b><br>"
            "Show or hide panels from View → Panels. Drag panel titles "
            "to rearrange them. Use View → Reset current layout "
            "to restore the default arrangement.</p>"
            "<p><b>Scripting</b><br>"
            "Choose Workspace → Mode → Explore for general Python plotting, "
            "or System to work with the selected system. "
            "Find sample scripts under Workspace → Examples and command "
            "references under System help and Workspace help.</p>"
            "<p><b>Saving and troubleshooting</b><br>"
            "Save system configurations in Presets and export solution data "
            "from Data view. Open View → Output panel for error messages.</p>",
        )

    def _rename_current_view(self):
        try:
            self.workspace_controller.rename_current_view()
        except ValueError as e:
            self.status_bar.set_temporary_app_message(str(e), error=True)

    def _restore_app_layout(self):
        settings = session_store.app_settings()
        self._set_theme(session_store.saved_theme(settings))
        session_store.restore(
            settings,
            self,
            self.dock_layout,
            self.jupyter_console_panel,
            self.status_bar,
        )
        self._set_workspace_mode(session_store.saved_mode(settings))

    def _reset_session_state(self):
        session_store.clear(session_store.app_settings())
        self.reset_session_state = True
        self.status_bar.set_temporary_app_message("Reset session state for next launch")

    def closeEvent(self, a0):
        if not self.jupyter_console_panel.script_panel.confirm_close():
            a0.ignore()
            return

        self.jupyter_console_panel.shutdown_kernel()
        self._set_orbit_mode(False)
        self.scene.animation_controller.stop()
        self.solver.shutdown()

        if not self.reset_session_state:
            session_store.save(
                session_store.app_settings(),
                self,
                self.dock_layout,
                self.jupyter_console_panel,
                self.status_bar,
                self.workspace_mode,
            )

        super().closeEvent(a0)
