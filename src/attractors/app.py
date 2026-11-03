# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .colour import colourmap
from .console import analysis
from .console.jupyter_console_panel import JupyterConsolePanel
from .console.live_plot_controller import LivePlotController
from .console.system import SystemInspector
from .console.workspace_controller import WorkspaceController
from .console.workspace_inspector import WorkspaceInspector
from .core.solution_validation import validate_solutions
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

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PARTIAL_N = 75000
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

        self._initial_full_solves = 0
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._restoring_view = False
        self._active_solve_request_id = None
        self._active_lyapunov_request_id = None
        self._system_solutions = []
        self._active_run = None
        self._analysis_run = None

        self._solve_state = {
            "solving": False,
            "valid": False,
            "stale": False,
            "partial": False,
            "last_error": None,
            "request_id": None,
            "attractor": None,
            "parameters": {},
            "n": None,
            "t_max": None,
            "trajectories": 0,
            "solution_points": [],
        }

        self._solve_perf_tokens = {}
        self._lyapunov_perf_tokens = {}
        self._last_projection_update = None
        self._last_live_preview_update = None
        self._latest_projection_solutions = None
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
        self._live_plots = {}
        self._live_items = {}
        self.live_plot_controller = LivePlotController(self)
        self.system = SystemInspector(self)

        self.solver = SolveManager(self)
        self.solver.solutions_ready.connect(self._on_solve_result)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)
        self.solver.lyapunov_failed.connect(self._on_lyapunov_failed)

        self.scene = ViewManager(self)
        self.scene.animation_segments_data.connect(
            lambda segments: self.live_plot_controller._refresh_live_preview(
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
        self.controls.solve_requested.connect(self._on_controls_solve_requested)
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
        self.main_toolbar = MainToolbar(self)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.main_toolbar)
        self.workspace_toolbar = WorkspaceToolbar(
            self.main_toolbar, self.system_toolbar, self.jupyter_console_panel
        )
        self.workspace_controller = WorkspaceController(self, self.workspace_toolbar)
        self.jupyter_console_panel.script_panel.status_changed.connect(
            lambda message: self.status_bar.set_temporary_app_message(message)
        )

        self.jupyter_console_panel.set_explore_status_callback(
            self.system_toolbar.set_status
        )
        self.system_toolbar.plot_requested.connect(
            self.live_plot_controller._on_plot_requested
        )
        self.system_toolbar.live_trace_remove_requested.connect(
            self.live_plot_controller._remove_live_trace
        )
        self.system_toolbar.live_plot_clear_requested.connect(
            self.live_plot_controller._clear_live_plot
        )
        self.jupyter_console_panel.plots.plots_changed.connect(
            self.live_plot_controller._on_plots_changed
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
        self.system_toolbar.set_solve_state(self._solve_state)
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
            (
                toolbar.solve_action.triggered,
                lambda: self._on_controls_solve_requested(True),
            ),
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
            (
                menu.solve_action.triggered,
                lambda: self._on_controls_solve_requested(True),
            ),
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
            (workspace.name_edit.returnPressed, controller.rename_current_view),
            (workspace.new_plot_action.triggered, controller.new_plot),
            (workspace.new_view3d_action.triggered, controller.new_view3d),
            (workspace.rename_action.triggered, controller.rename_current_view),
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
            self._clear_analysis_run()
            self.solver.cancel_solve()
            self.solver.cancel_lyapunov()
            self._solve_pending = False
            self._latest_projection_solutions = None
            self.scene.clear_solutions()
            self._clear_data_view()
            self.lyapunov_panel.clear()
            self._system_solutions = []
            self.phase_portrait.clear()

    def _rebuild_view_from_config(self, config):
        self.scene.animation_controller.stop()
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self._clear_analysis_run()
        self._restoring_view = True
        try:
            self.phase_portrait.clear()
            self._system_solutions = []
            self._latest_projection_solutions = None
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
        self._clear_analysis_run()
        self._restoring_view = True
        try:
            self.phase_portrait.clear()
            self._system_solutions = []
            self._latest_projection_solutions = None
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

    def _set_console_parameters(self, values, *, solve=False):
        config, current_values = self._get_current_config_and_values()
        if config is None:
            raise ValueError("No attractor selected")

        updates = self._validated_console_parameter_updates(config, values)
        next_values = {**current_values, **updates}
        self.controls.set_current_values(next_values)
        self.scene.viewport_overlay.set_info(
            config,
            self.controls.get_current_values(),
        )
        if solve:
            self._on_controls_solve_requested(True)
        elif self.controls.get_current_values() != current_values:
            self._mark_settings_unsolved()

        return self.system.parameters()

    def _set_console_time(self, *, n=None, t_max=None, solve=False):
        next_n = self.current_n if n is None else self._validated_console_n(n)
        next_t_max = (
            self.current_t_max
            if t_max is None
            else self._validated_console_t_max(t_max)
        )
        time_changed = next_n != self.current_n or next_t_max != self.current_t_max
        self.current_n = next_n
        self.current_t_max = next_t_max
        self.controls.set_time_values(self.current_n, self.current_t_max)
        self.controls.set_traj_tail_max(self.current_n)

        if solve:
            self._on_controls_solve_requested(True)
        elif time_changed:
            self._mark_settings_unsolved()

        return self.system.status()

    def _validated_console_n(self, value):
        try:
            n = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("N must be a positive integer") from exc
        if n < 1000 or n > 500000:
            raise ValueError("N must be between 1000 and 500000")

        return n

    def _validated_console_t_max(self, value):
        try:
            t_max = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("t_max must be a positive integer") from exc
        if t_max < 1 or t_max > 750:
            raise ValueError("t_max must be between 1 and 750")

        return t_max

    def _validated_console_parameter_updates(self, config, values):
        if not isinstance(values, dict):
            raise TypeError("Parameter updates must be a dictionary")

        params = {param.name: param for param in config.params}
        updates = {}
        for name, value in values.items():
            key = str(name)
            if key not in params:
                raise ValueError(f"Unknown parameter: {key}")
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter {key} must be numeric") from exc

            param = params[key]
            if numeric < param.min_val or numeric > param.max_val:
                raise ValueError(
                    f"Parameter {key} must be between {param.min_val} and {param.max_val}"
                )
            updates[key] = numeric

        return updates

    def _solve_from_console(self):
        self._on_controls_solve_requested(True)

        return self.system.status()

    def _mark_settings_unsolved(self):
        self.solver.cancel_solve()
        self._active_solve_request_id = None
        self._active_run = None
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._set_solve_state(
            solving=False,
            valid=False,
            stale=self._analysis_run is not None,
            partial=False,
            last_error=None,
        )

    def _clear_analysis_run(self):
        self._active_solve_request_id = None
        self._active_run = None
        self._analysis_run = None
        self.signal_panel.set_source(None, {})
        self.trajectory_analysis_panel.set_source(None, {})
        self.scene.set_playback_source(None)
        self.main_toolbar.anim_action.setEnabled(False)

    def _set_solve_state(self, **updates):
        state = dict(self._solve_state)
        state.update(updates)
        self._solve_state = state
        self.system_toolbar.set_solve_state(state)
        self.signal_panel.set_source(self._analysis_run, state)
        run = self._analysis_run
        self.trajectory_analysis_panel.set_source(run, state)

        playable = bool(
            run is not None
            and state.get("valid")
            and not state.get("stale")
            and not state.get("solving")
            and state.get("request_id") == run["request_id"]
            and len(run["variables"]) == 3
        )
        self.scene.set_playback_source(run if playable else None)
        self.main_toolbar.anim_action.setEnabled(playable)

        return state

    def _clear_data_view(self):
        self.controls.data_view.clear()

    def _update_data_view(self, solutions, is_partial):
        if is_partial:
            return

        config, values = self._get_current_config_and_values()
        t_min = 0.0 if config is None else config.time_defaults.t_min
        self.controls.data_view.set_solutions(
            solutions,
            t_min=t_min,
            t_max=self.current_t_max,
            trajectory_specs=self._solve_state.get("trajectory_specs", []),
            config=config,
            values=values,
            partial=is_partial,
        )

    def _update_plot(self):
        self.scene.animation_controller.stop()
        self.solver.cancel_solve()
        self.solver.cancel_lyapunov()
        self._solve_pending = False
        self._dispatch_solve(full=True)
        config, values = self._get_current_config_and_values()
        if config is not None:
            self.scene.viewport_overlay.set_info(config, values)

    def _partial_t_max(self, full_n, partial_n, full_t_max, t_min):
        if partial_n >= full_n:
            return full_t_max

        dt = (full_t_max - t_min) / full_n

        return t_min + partial_n * dt

    def _dispatch_solve(self, full=False):
        if self._solve_pending:
            return
        self._solve_pending = True
        self._solve_needed = False
        config, values = self._get_current_config_and_values()
        if config is None:
            self._solve_pending = False
            self._set_solve_state(
                solving=False,
                valid=False,
                stale=False,
                partial=False,
                last_error="No attractor selected",
                request_id=None,
                attractor=None,
                parameters={},
                n=None,
                t_max=None,
                trajectories=0,
                solution_points=[],
            )
            return
        full_record = full or any(
            self._panel_visible(name)
            for name in ("signal_panel", "trajectory_analysis_panel")
        )
        user_n = self.current_n or config.time_defaults.n
        t_max = self.current_t_max
        trajectories = self.controls.trajectory_panel.get_trajectories()

        if trajectories:
            trajectory_specs = []
            for trajectory in trajectories:
                trajectory_n = int(trajectory.get("n", user_n))
                trajectory_t_max = float(trajectory.get("t_max", t_max))
                solve_n = trajectory_n if full_record else min(trajectory_n, PARTIAL_N)
                solve_t_max = (
                    trajectory_t_max
                    if full_record
                    else self._partial_t_max(
                        trajectory_n,
                        solve_n,
                        trajectory_t_max,
                        config.time_defaults.t_min,
                    )
                )
                trajectory_specs.append(
                    {
                        "ic": [float(coord) for coord in trajectory["ic"]],
                        "n": solve_n,
                        "t_max": solve_t_max,
                    }
                )
        else:
            solve_n = int(user_n if full_record else min(user_n, PARTIAL_N))
            solve_t_max = (
                t_max
                if full_record
                else self._partial_t_max(
                    user_n, solve_n, t_max, config.time_defaults.t_min
                )
            )
            trajectory_specs = [
                {
                    "ic": [float(coord) for coord in config.initial_conditions],
                    "n": solve_n,
                    "t_max": solve_t_max,
                }
            ]

        dispatch_n = max(spec["n"] for spec in trajectory_specs)
        dispatch_t_max = max(spec["t_max"] for spec in trajectory_specs)
        self.solver.cancel_lyapunov()

        if full:
            n_trajectories = len(trajectory_specs)
            status_text = (
                "Solving trajectory"
                if n_trajectories == 1
                else f"Solving {n_trajectories} trajectories"
            )
            self.status_bar.set_app_message(status_text)

        signature = {
            "attractor": config.name,
            "parameters": {str(key): float(value) for key, value in values.items()},
            "n": int(dispatch_n),
            "t_max": float(dispatch_t_max),
            "trajectories": [
                [float(coord) for coord in spec["ic"]] for spec in trajectory_specs
            ],
            "trajectory_specs": [
                {
                    "ic": [float(coord) for coord in spec["ic"]],
                    "n": int(spec["n"]),
                    "t_max": float(spec["t_max"]),
                }
                for spec in trajectory_specs
            ],
        }

        request_id = self.solver.next_solve_request_id()
        self._active_solve_request_id = request_id

        self._active_run = {
            **signature,
            "request_id": request_id,
            "t_min": config.time_defaults.t_min,
            "variables": config.variables,
            "labels": tuple(t["label"] for t in trajectories) or ("T0",),
            "colours": tuple(t["colour"].name() for t in trajectories) or (None,),
            "analysis_ready": full_record,
        }

        self._set_solve_state(
            solving=True,
            valid=False,
            stale=bool(self._system_solutions),
            partial=not full,
            last_error=None,
            request_id=request_id,
            attractor=signature["attractor"],
            parameters=signature["parameters"],
            n=signature["n"],
            t_max=signature["t_max"],
            trajectories=len(trajectory_specs),
            trajectory_specs=signature["trajectory_specs"],
            solution_points=[],
        )
        token = perf_start(
            self,
            "solve.request",
            key=request_id,
            attractor=config.name,
            full=full,
            partial=not full,
            n=dispatch_n,
            t_max=dispatch_t_max,
            trajectories=len(trajectory_specs),
        )
        if token is not None:
            self._solve_perf_tokens[request_id] = token

        self.solver.request_solve(
            request_id,
            config,
            values,
            trajectory_specs,
            dispatch_n,
            not full,
            dispatch_t_max,
        )

    def _on_controls_solve_requested(self, full):
        self.scene.animation_controller.stop()
        if not full and self._solve_pending and self._solve_state.get("partial", False):
            self._solve_needed = True
            self._full_needed = False

            return

        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = full
        self._full_needed = full
        self._dispatch_solve(full=full)

    def _request_lyapunov(self, config=None, values=None):
        if not self._panel_visible("lyapunov_panel"):
            return

        if config is None or values is None:
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

    def _on_solve_result(self, request_id, solutions, is_partial):
        if request_id != self._active_solve_request_id:
            return

        solve_token = self._solve_perf_tokens.pop(request_id, None)
        self._solve_pending = False

        if solutions is None:
            perf_finish(self, solve_token, status="failed", partial=is_partial)
            self._set_solve_state(
                solving=False,
                valid=False,
                stale=bool(self._system_solutions),
                partial=False,
                last_error="Solve failed",
                solution_points=[],
            )
            if not is_partial:
                self._clear_data_view()
            if self._solve_needed:
                self._solve_needed = False
                self._dispatch_solve(full=self._full_needed)
            else:
                self.status_bar.set_app_message("Solve failed", error=True)
            return

        config, _values = self._get_current_config_and_values()
        if config is None:
            perf_finish(self, solve_token, status="discard")
            return

        validation_start = time.perf_counter()
        is_valid, message = validate_solutions(solutions, dimension=config.dimension)

        validation_ms = (time.perf_counter() - validation_start) * 1000
        if not is_valid:
            perf_finish(self, solve_token, status="invalid", partial=is_partial)
            self._set_solve_state(
                solving=False,
                valid=False,
                stale=bool(self._system_solutions),
                partial=False,
                last_error=message,
                solution_points=[],
            )
            if not is_partial:
                self._clear_data_view()
            self.status_bar.set_app_message(message, error=True)
            if self._solve_needed:
                self._solve_needed = False
                full = self._full_needed
                self._full_needed = False
                self._dispatch_solve(full=full)
            return

        perf_finish(self, solve_token, status="ok", partial=is_partial)

        ui_start = time.perf_counter()

        self.status_bar.clear_app_message()
        config, _values = self._get_current_config_and_values()
        self._display_system_solution(config, solutions, is_partial)

        if self._active_run["analysis_ready"]:
            arrays = []
            for solution in solutions:
                view = solution.view()
                view.setflags(write=False)
                arrays.append(view)

            self._analysis_run = {**self._active_run, "solutions": tuple(arrays)}

        self._update_data_view(solutions, is_partial)
        self._set_solve_state(
            solving=False,
            valid=not is_partial,
            stale=is_partial or bool(self._solve_needed),
            partial=is_partial,
            last_error=None,
            solution_points=[len(solution) for solution in solutions or []],
        )

        if is_partial:
            self.live_plot_controller._refresh_live_preview(solutions)
            self._update_projection_panel_from_solutions(solutions)

        if not is_partial:
            self._latest_projection_solutions = solutions
            self._update_projection_panel_from_solutions(solutions)
            if (
                self._panel_visible("projection_panel")
                and self._initial_full_solves == 0
            ):
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1

            if config.dimension == 3:
                self.scene.grid_overlay.auto_adjust_grid(solutions)
                # self.scene.camera_controller.fit_camera_to_solutions(solutions)

        if not is_partial:
            if self.lyapunov_panel.auto_enabled():
                self._request_lyapunov()

            config, values = self._get_current_config_and_values()
            if self._panel_visible("poincare_panel"):
                self.poincare_panel.set_attractor(config, values)

            self.bifurcation_panel.current_values = dict(values)

            self._last_live_preview_update = None
            for plot_name in list(self.live_plot_controller.live_plots):
                self.live_plot_controller._refresh_live_plot(plot_name)

        ui_ms = (time.perf_counter() - ui_start) * 1000
        if self._perf.enabled:
            self._perf._logger.info(
                "solve.ui completed in %.3f ms (request_id=%s partial=%s validation_ms=%.3f)",
                ui_ms,
                request_id,
                is_partial,
                validation_ms,
            )

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

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

    def _display_system_solution(self, config, solutions, is_partial):
        self._select_system_view(config)
        self._system_solutions = solutions

        if config.dimension == 2:
            self.phase_portrait.set_trajectories(
                self.controls.trajectory_panel.get_trajectories()
            )
            self.phase_portrait.display_solutions(
                solutions,
                initial_conditions=self._active_run["trajectories"],
            )
            self.phase_portrait.request_field_update()
            return

        self.scene.trajectory_renderer.set_time_steps(self._trajectory_time_steps())
        self.scene.display_solutions(solutions, is_partial)

        if self.main_toolbar.auto_fit_camera_action.isChecked():
            self.scene.camera_controller.fit_camera_to_solutions(solutions)
            self.scene.grid_overlay.auto_adjust_grid(solutions)

    def _trajectory_time_steps(self):
        config, _values = self._get_current_config_and_values()
        if config is None:
            return []

        t_min = config.time_defaults["t_min"]
        trajectories = self.controls.trajectory_panel.get_trajectories()

        if trajectories:
            return [
                (trajectory["t_max"] - t_min) / trajectory["n"]
                for trajectory in trajectories
            ]

        return [(self.current_t_max - t_min) / self.current_n]

    def _reapply_projections(self):
        config, _values = self._get_current_config_and_values()
        if config is None:
            return

        solutions = (
            self._latest_projection_solutions
            or self.scene.trajectory_renderer.solutions
        )
        self.projection_panel.reapply_projections(solutions)

    def _update_projection_panel_from_solutions(self, solutions):
        config, _values = self._get_current_config_and_values()
        if config is None:
            return

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
        config, _values = self._get_current_config_and_values()
        if config is None or config.dimension != 3:
            return

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

        self._clear_analysis_run()
        self._latest_projection_solutions = None

        config, _values = self._get_current_config_and_values()
        if config is None or config.dimension == 3:
            self.scene.clear_solutions()
            self._system_solutions = []

        self._clear_data_view()
        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

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
                QtCore.QTimer.singleShot(0, self._reapply_projections)
            elif name == "poincare_panel":
                config, values = self._get_current_config_and_values()
                self.poincare_panel.set_attractor(config, values)
                self.poincare_panel.recompute()
            elif name == "bifurcation_panel":
                config, values = self._get_current_config_and_values()
                if config is not None:
                    self.bifurcation_panel.set_config(config, values)
            elif name == "trajectory_analysis_panel" and (
                self._analysis_run is None or self._solve_state.get("partial")
            ):
                self._on_controls_solve_requested(True)
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
