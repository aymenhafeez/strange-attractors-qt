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
from .ui.bifurcation_panel import BifurcationPanel
from .ui.control_panel import ControlPanel
from .ui.docking import DockLayout
from .ui.icons import icon
from .ui.lyapunov_panel import LyapunovPanel
from .ui.main_toolbar import build_menu_bar, build_status_bar, build_toolbar
from .ui.output_panel import OutputPanel
from .ui.phase_panel import PhasePortraitPanel
from .ui.poincare_panel import PoincarePanel
from .ui.projection_panel import ProjectionPanel
from .ui.right_panel import RightPanel
from .ui.signal_panel import SignalPanel
from .ui.startup import WelcomeDialog
from .ui.style import MAIN_WINDOW, plot_colours
from .ui.system_toolbar import SystemToolbar
from .view.view_manager import ViewManager
from .workers.solve_manager import SolveManager

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PARTIAL_N = 75000
PROJECTION_UPDATE_INTERVAL = 100  # ms


def _panel_visible(window, panel_name):
    return not window._panel_docks[panel_name].isHidden()


def _workspace_visible(window):
    return any(not dock.isHidden() for dock in window._workspace_docks())


def app_settings():
    return QtCore.QSettings("Aymen Hafeez", "Systems analysis")


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
        self._process_status_visible = True
        self._app_status_message = ""
        self._app_status_error = False
        self._signal_status_message = ""
        self._signal_status_error = False
        self._app_status_clear_timer = None
        self._output_panel_visible = False
        self._panel_docks = {}
        self._open_analysis_panels = set()
        self._jupyter_toolbar_actions = []
        self.system_toolbar_action = None
        self._menu_actions = []
        self.workspace_system_mode_action = None
        self.workspace_explore_mode_action = None
        self.workspace_mode = "system"
        self.workspace_crosshair_action = None
        self._explore_toolbar_actions = []
        self._connected_explorer = None

        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = next(iter(ATTRACTORS.keys()))
        self._custom_config = None

        self.auto_fit_camera = True

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
        self.workspace_controller = WorkspaceController(self)
        self.system = SystemInspector(self)

        self.solver = SolveManager(self)
        self.solver.solutions_ready.connect(self._on_solve_result)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)
        self.solver.lyapunov_failed.connect(self._on_lyapunov_failed)

        self.scene = ViewManager(self)
        self.scene.animation_finished.connect(
            lambda: self._sync_toolbar_animation_action(False)
        )
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
        self.lyapunov_panel.close_requested.connect(self._close_lyapunov_panel)

        self.projection_panel = ProjectionPanel()
        self.projection_panel.close_requested.connect(self._close_projections)

        self.bifurcation_panel = BifurcationPanel()
        self.bifurcation_panel.close_requested.connect(self._close_bifurcation)

        self.signal_panel = SignalPanel()

        self.output_panel = OutputPanel()
        self.output_panel.hide()

        self.jupyter_console_panel = JupyterConsolePanel(
            self.dock_layout,
            self._jupyter_console_namespace,
            script_dir=self._scripts_directory,
        )
        self.system_toolbar = SystemToolbar()
        self.jupyter_console_panel.script_panel.status_changed.connect(
            lambda message: self._set_temporary_app_status(message)
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
        self.jupyter_console_panel.plots.current_changed.connect(
            lambda _name: self._sync_explore_actions()
        )
        self.jupyter_console_panel.active_view_changed.connect(
            self._sync_explore_actions
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
        self.jupyter_console_panel.views3d.current_changed.connect(
            lambda _name: self._sync_explore_actions()
        )
        self.jupyter_console_panel.tables.tables_changed.connect(
            self._sync_jupyter_workspace_state
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
        ):
            self._panel_docks[name] = self.dock_layout.add(
                f"analysis/{name}", title, panel
            )
        self.output_dock = self.dock_layout.add("output", "Output", self.output_panel)
        build_toolbar(self)
        build_menu_bar(self)
        self.controls.animation_mode_changed.connect(self._set_animation_mode)
        build_status_bar(self)

        self.signal_panel.status_changed.connect(self._set_signal_status)

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
            self._set_output_panel_visible(True)

    def _on_poincare_plane_changed(self, axis, value):
        self.scene.grid_overlay.remove_poincare_plane()
        self.phase_portrait.set_section()

        config, _values = self._get_current_config_and_values()
        if (
            config is None
            or axis not in config.variables
            or not _panel_visible(self, "poincare_panel")
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
            self._set_app_status(str(e), error=True)
            return

        if not added:
            self._set_app_status("Trajectory limit reached", error=True)

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
            self._set_app_status(str(e), error=True)
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
        self._sync_toolbar_animation_action(False)
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
        self._sync_toolbar_animation_action(False)
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
            self._sync_toolbar_animation_action(False)
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
        with (
            QtCore.QSignalBlocker(self.workspace_system_mode_action),
            QtCore.QSignalBlocker(self.workspace_explore_mode_action),
        ):
            self.workspace_system_mode_action.setChecked(mode == "system")
            self.workspace_explore_mode_action.setChecked(mode == "explore")

    def _toggle_system_workspace(self):
        if self.workspace_mode != "system":
            self._set_workspace_mode("system")
            if _workspace_visible(self):
                return
        elif _workspace_visible(self):
            side_docks = [self.parameters_dock, self.right_panel.trajectory_dock]
            widths = [dock.width() for dock in side_docks]
            for dock in self._workspace_docks():
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
        self._set_temporary_app_status(f"Restored {self.workspace_mode.title()} layout")

    def _hide_menu_icons(self, menu):
        for action in menu.actions():
            action.setIconVisibleInMenu(False)
            submenu = action.menu()
            if submenu is not None:
                self._hide_menu_icons(submenu)

    def _add_menu_action(self, menu, text, source_action):
        action = QtGui.QAction(text, self)
        action.setCheckable(source_action.isCheckable())
        action.setToolTip(source_action.toolTip())
        action.triggered.connect(
            lambda checked=False, source_action=source_action: source_action.trigger()
        )
        menu.addAction(action)
        self._menu_actions.append((action, source_action))
        self._sync_menu_action(action, source_action)

        return action

    def _sync_menu_action(self, action, source_action):
        action.setEnabled(source_action.isEnabled())
        if action.isCheckable():
            with QtCore.QSignalBlocker(action):
                action.setChecked(source_action.isChecked())

    def _sync_menu_actions(self):
        for action, source_action in self._menu_actions:
            self._sync_menu_action(action, source_action)

    def _set_theme(self, theme):
        app = QtWidgets.QApplication.instance()
        if app is None:
            return

        app.setProperty("appTheme", theme)
        self._sync_theme_actions(theme)
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

    def _sync_theme_actions(self, theme):
        with (
            QtCore.QSignalBlocker(self.view_system_action),
            QtCore.QSignalBlocker(self.view_light_action),
            QtCore.QSignalBlocker(self.view_dark_action),
        ):
            self.view_system_action.setChecked(theme is None)
            self.view_light_action.setChecked(theme == "light")
            self.view_dark_action.setChecked(theme == "dark")

    def _add_checked_toolbar_action(
        self,
        toolbar,
        text,
        checked,
        callback,
        tooltip,
        *,
        icon=None,
    ):
        if icon is None:
            action = toolbar.addAction(text)
        else:
            action = toolbar.addAction(icon, text)
        action.setCheckable(True)
        action.setChecked(bool(checked))
        action.setToolTip(tooltip)
        action.toggled.connect(callback)
        return action

    def _add_checked_icon_toolbar_action(
        self, toolbar, icon, checked, callback, tooltip
    ):
        action = toolbar.addAction(icon, "")
        action.setCheckable(True)
        action.setChecked(bool(checked))
        action.setToolTip(tooltip)
        action.toggled.connect(callback)
        self._keep_toolbar_action_from_taking_focus(toolbar, action)
        return action

    def _set_left_panel_visible(self, checked):
        for dock in self._left_docks:
            dock.setVisible(checked)

    def _set_output_panel_visible(self, visible):
        self.output_dock.setVisible(visible)
        self._output_panel_visible = bool(visible)
        self._sync_output_panel_action()

    def _toggle_output_panel(self):
        self._set_output_panel_visible(not self._output_panel_visible)

    def _sync_output_panel_action(self):
        if not hasattr(self, "output_panel_action"):
            return

        with QtCore.QSignalBlocker(self.output_panel_action):
            self.output_panel_action.setChecked(self._output_panel_visible)

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
        self._sync_toolbar_animation_action(False)

        particle_flow = mode == "particle"

        self.controls.set_particle_options_visible(particle_flow)
        self.toolbar_loop_action.setEnabled(not particle_flow)
        self.toolbar_point_action.setEnabled(not particle_flow)

        with (
            QtCore.QSignalBlocker(self.animation_traj_action),
            QtCore.QSignalBlocker(self.animation_particle_flow_action),
        ):
            self.animation_traj_action.setChecked(not particle_flow)
            self.animation_particle_flow_action.setChecked(particle_flow)

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

    def _add_panel_menu_action(self, text, callback):
        action = QtGui.QAction(text, self)
        action.setCheckable(True)
        action.triggered.connect(lambda _checked=False: callback())
        return action

    def _sync_toolbar_panel_actions(self):
        with (
            QtCore.QSignalBlocker(self.toolbar_lyapunov_action),
            QtCore.QSignalBlocker(self.toolbar_projection_action),
            QtCore.QSignalBlocker(self.toolbar_poincare_action),
            QtCore.QSignalBlocker(self.toolbar_bifurcation_action),
            QtCore.QSignalBlocker(self.toolbar_explore_action),
            QtCore.QSignalBlocker(self.toolbar_system_action),
            QtCore.QSignalBlocker(self.toolbar_process_status_action),
            QtCore.QSignalBlocker(self.output_panel_action),
        ):
            self.toolbar_lyapunov_action.setChecked(
                _panel_visible(self, "lyapunov_panel")
            )
            self.toolbar_projection_action.setChecked(
                _panel_visible(self, "projection_panel")
            )
            self.toolbar_poincare_action.setChecked(
                _panel_visible(self, "poincare_panel")
            )
            self.toolbar_bifurcation_action.setChecked(
                _panel_visible(self, "bifurcation_panel")
            )
            self.toolbar_explore_action.setChecked(self.workspace_mode == "explore")
            self.toolbar_system_action.setChecked(
                self.workspace_mode == "system" and _workspace_visible(self)
            )
            self.toolbar_process_status_action.setChecked(self._process_status_visible)
            self.output_panel_action.setChecked(self._output_panel_visible)
        self._sync_jupyter_workspace_state()

    def _set_process_status_visible(self, visible):
        self._process_status_visible = bool(visible)

        self.process_status.setVisible(self._process_status_visible)
        self.process_status.set_active(self._process_status_visible)
        self.statusBar().setVisible(self._process_status_visible)

        if (
            self.toolbar_process_status_action.isChecked()
            != self._process_status_visible
        ):
            with QtCore.QSignalBlocker(self.toolbar_process_status_action):
                self.toolbar_process_status_action.setChecked(
                    self._process_status_visible
                )

        self._sync_status_bar_visibility()

    def _toggle_process_status(self):
        self._set_process_status_visible(not self._process_status_visible)

    def _set_app_status(self, message, error=False):
        self._app_status_message = str(message)
        self._app_status_error = error
        self._refresh_app_status()

    def _set_temporary_app_status(self, message, *, timeout_ms=3000, error=False):
        message = str(message)
        self._set_app_status(message, error=error)

        if self._app_status_clear_timer is None:
            self._app_status_clear_timer = QtCore.QTimer(self)
            self._app_status_clear_timer.setSingleShot(True)

        try:
            self._app_status_clear_timer.timeout.disconnect()
        except TypeError:
            pass

        self._app_status_clear_timer.timeout.connect(
            lambda expected=message: (
                self._clear_app_status()
                if self._app_status_message == expected
                else None
            )
        )
        self._app_status_clear_timer.start(int(timeout_ms))

    def _clear_app_status(self):
        self._app_status_message = ""
        self._app_status_error = False
        self._refresh_app_status()

    def _set_signal_status(self, message, error=False):
        self._signal_status_message = str(message)
        self._signal_status_error = error
        self._refresh_app_status()

    def _refresh_app_status(self):
        messages = [
            message
            for message in (
                self._app_status_message,
                self._signal_status_message,
            )
            if message
        ]
        text = " · ".join(messages)

        has_error = (bool(self._app_status_message) and self._app_status_error) or (
            bool(self._signal_status_message) and self._signal_status_error
        )
        colour = "#ff6b6b" if has_error else "#178640"

        self.app_status_label.setText(text)
        self.app_status_label.setToolTip(text)
        self.app_status_label.setStyleSheet(
            f"border: none; padding: 0 4px 3px 4px; font-size: 12px; color: {colour};"
        )
        self._sync_status_bar_visibility()

    def _sync_status_bar_visibility(self):
        self.statusBar().setVisible(
            bool(
                self._process_status_visible
                or self._app_status_message
                or self._signal_status_message
            )
        )

    def _build_jupyter_toolbar_actions(self, toolbar):
        self._jupyter_toolbar_actions = []
        toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        plot_item = self.jupyter_console_panel.plot_widget.getPlotItem()
        view_box = plot_item.getViewBox()

        self.plot_view_all_action = QtGui.QAction(
            icon("zoom-fit-best"),
            "View all",
            self,
        )
        self.plot_view_all_action.setToolTip("Fit all plot data")
        self.plot_view_all_action.triggered.connect(view_box.autoRange)

        mouse_group = QtGui.QActionGroup(self)
        mouse_group.setExclusive(True)
        self.plot_pan_action = QtGui.QAction(
            icon("transform-move"),
            "Pan",
            self,
        )
        self.plot_pan_action.setCheckable(True)
        self.plot_pan_action.setChecked(True)
        self.plot_pan_action.setToolTip("Pan with left mouse button")
        self.plot_zoom_action = QtGui.QAction(
            icon("zoom-in"),
            "Zoom",
            self,
        )
        self.plot_zoom_action.setCheckable(True)
        self.plot_zoom_action.setToolTip("Zoom to rectangle with left mouse button")
        mouse_group.addAction(self.plot_pan_action)
        mouse_group.addAction(self.plot_zoom_action)
        self.plot_pan_action.triggered.connect(
            lambda: view_box.setLeftButtonAction("pan")
        )
        self.plot_zoom_action.triggered.connect(
            lambda: view_box.setLeftButtonAction("rect")
        )

        self.plot_x_grid_action = self._plot_option_action(
            "X grid",
            plot_item.ctrl.xGridCheck,
        )
        self.plot_y_grid_action = self._plot_option_action(
            "Y grid",
            plot_item.ctrl.yGridCheck,
        )

        self._add_jupyter_plot_controls(toolbar)
        self.plot_options_menu = plot_item.getMenu()
        self.plot_view_menu = view_box.menu

        for action in self._jupyter_toolbar_actions:
            action.setVisible(False)

    def _add_jupyter_plot_controls(self, toolbar):
        label = QtWidgets.QLabel(" View: ")
        label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._jupyter_toolbar_actions.append(toolbar.addWidget(label))

        self.toolbar_workspace_combo = QtWidgets.QComboBox()
        self.toolbar_workspace_combo.setMinimumWidth(50)
        self.toolbar_workspace_combo.setMaximumWidth(130)
        self.toolbar_workspace_combo.currentIndexChanged.connect(
            lambda _index: self.workspace_controller.on_toolbar_view_selected()
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_workspace_combo)
        )

        self.toolbar_workspace_name = QtWidgets.QLineEdit()
        self.toolbar_workspace_name.setPlaceholderText("Plot name")
        self.toolbar_workspace_name.setMaximumWidth(130)
        self.toolbar_workspace_name.returnPressed.connect(
            lambda: self.workspace_controller.rename_current_view()
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_workspace_name)
        )

        icon_specs = [
            (
                "Rename",
                "edit-rename",
                lambda: self.workspace_controller.rename_current_view(),
                "Rename the current workspace view",
            ),
            (
                "Clear",
                "edit-clear-history",
                lambda: self.workspace_controller.clear_current_view(),
                "Clear the current view",
            ),
            (
                "Clear all",
                "edit-delete",
                lambda: self.workspace_controller.clear_all_views(),
                "Clear all views",
            ),
            (
                "Fit",
                "view-fullscreen",
                lambda: self.workspace_controller.fit_current_view(),
                "Fit current view",
            ),
            (
                "Reset",
                "zoom-original",
                lambda: self.workspace_controller.reset_current_view(),
                "Reset camera",
            ),
        ]

        new_button = QtWidgets.QToolButton()
        new_button.setText("New")
        new_button.setIcon(icon("list-add"))
        new_button.setToolTip("Create a new workspace view")
        new_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

        new_menu = QtWidgets.QMenu(new_button)
        new_plot_action = new_menu.addAction("New 2D plot")
        new_plot_action.triggered.connect(lambda: self.workspace_controller.new_plot())
        new_view3d_action = new_menu.addAction("New 3D view")
        new_view3d_action.triggered.connect(
            lambda: self.workspace_controller.new_view3d()
        )
        new_button.setMenu(new_menu)

        new_action = toolbar.addWidget(new_button)
        self._jupyter_toolbar_actions.append(new_action)

        for text, icon_name, callback, tooltip in icon_specs:
            action = toolbar.addAction(
                icon(icon_name),
                text,
            )
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            self._jupyter_toolbar_actions.append(action)
            self._keep_toolbar_action_from_taking_focus(toolbar, action)
            if text == "Rename":
                spacer = QtWidgets.QWidget()
                spacer.setSizePolicy(
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    QtWidgets.QSizePolicy.Policy.Preferred,
                )
                self._jupyter_toolbar_actions.append(toolbar.addWidget(spacer))
        self.workspace_controller.sync_views()
        self._keep_toolbar_action_from_taking_focus(toolbar, new_action)

        self.workspace_grid_action = toolbar.addAction(
            icon("view-grid"),
            "Grid",
        )
        self.workspace_grid_action.setCheckable(True)
        self.workspace_grid_action.setChecked(True)
        self.workspace_grid_action.setToolTip("Toggle grid visibility")
        self.workspace_grid_action.toggled.connect(
            self.workspace_controller.set_current_grid_visible
        )
        self._jupyter_toolbar_actions.append(self.workspace_grid_action)

        self.workspace_orbit_action = toolbar.addAction(
            icon("object-rotate-right"),
            "Orbit",
        )
        self.workspace_orbit_action.setCheckable(True)
        self.workspace_orbit_action.setChecked(False)
        self.workspace_orbit_action.setToolTip("Toggle current view orbit mode")
        self.workspace_orbit_action.toggled.connect(
            self.workspace_controller.set_current_view_orbit
        )
        self._jupyter_toolbar_actions.append(self.workspace_orbit_action)

        self._keep_toolbar_action_from_taking_focus(toolbar, self.workspace_grid_action)
        self.workspace_controller.sync_grid_action()

        self.workspace_crosshair_action = toolbar.addAction(
            icon("crosshairs"),
            "Crosshair",
        )
        self.workspace_crosshair_action.setCheckable(True)
        self.workspace_crosshair_action.setToolTip("Show plot crosshair coordinates")
        self.workspace_crosshair_action.toggled.connect(
            self.workspace_controller.set_current_crosshair_visible
        )
        self._jupyter_toolbar_actions.append(self.workspace_crosshair_action)
        self._keep_toolbar_action_from_taking_focus(
            toolbar, self.workspace_crosshair_action
        )
        self.workspace_controller.sync_crosshair_action()

        self.explore_trace_button = QtWidgets.QToolButton()
        self.explore_trace_button.setText("Traces: 0")
        self.explore_trace_button.setToolTip(
            "Manage reactive traces for the current view"
        )
        self.explore_trace_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.explore_trace_menu = QtWidgets.QMenu(self.explore_trace_button)
        self.explore_trace_button.setMenu(self.explore_trace_menu)
        trace_action = toolbar.addWidget(self.explore_trace_button)

        self.explore_clear_sliders_action = toolbar.addAction(
            icon("edit-clear"),
            "Sliders",
            self._clear_current_explore_sliders,
        )
        self.explore_clear_sliders_action.setToolTip(
            "Clear sliders for the current view"
        )

        self.explore_clear_state_action = toolbar.addAction(
            icon("edit-delete"),
            "Explore",
            self._clear_current_explore,
        )
        self.explore_clear_state_action.setToolTip(
            "Clear sliders and reactive traces for the current view"
        )

        self._jupyter_toolbar_actions.extend(
            [
                trace_action,
                self.explore_clear_sliders_action,
                self.explore_clear_state_action,
            ]
        )
        self._explore_toolbar_actions.extend(
            [
                trace_action,
                self.explore_clear_sliders_action,
                self.explore_clear_state_action,
            ]
        )

    def _sync_explore_actions(self):
        # putting this check in while refactoring the toolbar actions
        if not self._explore_toolbar_actions:
            return

        explore_visible = self.workspace_mode == "explore" and _workspace_visible(self)

        for action in self._explore_toolbar_actions:
            action.setVisible(explore_visible)

        if not explore_visible:
            return

        explorer = self.jupyter_console_panel.active_explorer()
        if self._connected_explorer is not explorer:
            if self._connected_explorer is not None:
                try:
                    self._connected_explorer.changed.disconnect(
                        self._sync_explore_actions
                    )
                except TypeError:
                    pass
            self._connected_explorer = explorer
            self._connected_explorer.changed.connect(self._sync_explore_actions)

        trace_names = explorer.trace_names()
        slider_names = explorer.slider_names()
        animation_names = explorer.animation_names()

        self.explore_trace_button.setText(f"Traces: {len(trace_names)}")
        self.explore_clear_sliders_action.setEnabled(bool(slider_names))
        self.explore_clear_state_action.setEnabled(
            bool(trace_names or slider_names or animation_names)
        )

        self.explore_trace_menu.clear()
        if not trace_names:
            action = self.explore_trace_menu.addAction("No traces")
            action.setEnabled(False)
            return

        for name in trace_names:
            action = self.explore_trace_menu.addAction(f"Remove {name}")
            action.triggered.connect(
                lambda _checked=False, name=name: self._remove_current_explore_trace(
                    name
                )
            )

    def _keep_toolbar_action_from_taking_focus(self, toolbar, action):
        widget = toolbar.widgetForAction(action)
        if widget is not None:
            widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def _plot_option_action(self, text, widget):
        action = QtGui.QAction(text, self)
        action.setCheckable(True)
        action.setChecked(widget.isChecked())
        action.toggled.connect(widget.setChecked)
        widget.toggled.connect(action.setChecked)
        return action

    def _popup_menu(self, menu):
        if menu is not None:
            menu.popup(QtGui.QCursor.pos())

    def _add_proxy_menu(self, parent_menu, title, source_menu):
        menu = parent_menu.addMenu(title)
        self._populate_proxy_menu(menu, source_menu)

        return menu

    def _populate_examples_menu(self, menu):
        menu.clear()

        scripts = self.jupyter_console_panel.script_panel.example_scripts()
        if not scripts:
            action = menu.addAction("No examples available")
            action.setEnabled(False)
            return

        example_labels = {
            "plotting_methods_example.py": "Plotting methods",
            "curve_example.py": "Reactive curves",
            "lissajous_example.py": "Lissajous curve",
            "fourier_example.py": "Fourier series",
            "dejong_attractor_example.py": "De Jong attractor",
            "param_sweep_example.py": "Parameter sweep",
            "3d_lissajous_example.py": "3D Lissajous curve",
            "3d_pendulum.py": "3D pendulum animation",
            "surface_example.py": "Surface and wireframe plot",
        }

        for path in scripts:
            label = example_labels.get(path.name, path.stem.replace("_", " ").title())
            action = menu.addAction(label)
            action.setToolTip(str(path))
            action.triggered.connect(
                lambda _checked=False, path=path: self._open_example_script(path)
            )

    def _open_example_script(self, path):
        if self.jupyter_console_panel.script_panel.load_script(path):
            self._set_workspace_mode("explore")
            self._set_temporary_app_status(f"Opened example: {path.name}")

    def _populate_proxy_menu(self, menu, source_menu):
        source_actions = source_menu.actions()
        if any(
            isinstance(action, QtWidgets.QWidgetAction) for action in source_actions
        ):
            menu.addAction(
                f"Open {source_menu.title()}...",
                lambda checked=False, menu=source_menu: self._popup_menu(menu),
            )
            return

        for source_action in source_actions:
            if source_action.isSeparator():
                menu.addSeparator()
                continue

            source_submenu = source_action.menu()
            if source_submenu is not None:
                submenu = menu.addMenu(source_action.text())
                self._populate_proxy_menu(submenu, source_submenu)
                continue

            action = menu.addAction(source_action.text())
            action.setCheckable(source_action.isCheckable())
            action.setChecked(source_action.isChecked())
            action.setEnabled(source_action.isEnabled())
            action.triggered.connect(source_action.trigger)

    def _add_toolbar_menu_button(self, toolbar, text, menu, tooltip=None):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        return toolbar.addWidget(button)

    def _sync_jupyter_toolbar_visibility(self):
        visible = _workspace_visible(self)
        system_mode = self.workspace_mode == "system"

        for action in self._system_viewport_toolbar_actions:
            action.setVisible(system_mode)

        for action in self._jupyter_toolbar_actions:
            action.setVisible(visible)

        if self.system_toolbar_action is not None:
            self.system_toolbar_action.setVisible(visible and system_mode)

        self._sync_explore_actions()

    def _sync_jupyter_workspace_state(self):
        self._sync_jupyter_toolbar_visibility()

    def _sync_toolbar_animation_action(self, playing):
        if playing:
            self.toolbar_anim_action.setIcon(icon("media-playback-stop"))
            self.toolbar_anim_action.setText("Stop")
            self.toolbar_anim_action.setToolTip("Stop animation")
        else:
            self.toolbar_anim_action.setIcon(icon("media-playback-start"))
            self.toolbar_anim_action.setText("Play")
            self.toolbar_anim_action.setToolTip("Play animation")

    def _open_preset_folder(self):
        Path(self._preset_directory).mkdir(parents=True, exist_ok=True)
        opened = QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(self._preset_directory)
        )
        if not opened:
            self._set_app_status("Could not open preset folder", error=True)

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
            self._set_app_status("No attractor selected", error=True)
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
            self._set_app_status(str(exc), error=True)
            return

        self._refresh_presets(preset_name)
        self._set_app_status(f"Saved preset: {preset_name}")

    def _load_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self._set_app_status("Select a preset to load", error=True)
            return

        try:
            config, values, n, t_max = load_named_preset(
                self._preset_directory, preset_name
            )
        except PresetError as exc:
            self._set_app_status(str(exc), error=True)
            return

        self._apply_loaded_preset(config, values, n, t_max)
        self._refresh_presets(preset_name)
        self._set_app_status(f"Loaded preset: {preset_name}")

    def _delete_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self._set_app_status("Select a preset to delete", error=True)
            return

        try:
            delete_named_preset(self._preset_directory, preset_name)
        except PresetError as exc:
            self._set_app_status(str(exc), error=True)
            return

        self._refresh_presets()
        self._set_app_status(f"Deleted preset: {preset_name}")

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

    def _set_solve_state(self, **updates):
        state = dict(self._solve_state)
        state.update(updates)
        self._solve_state = state
        self.system_toolbar.set_solve_state(state)
        self.signal_panel.set_source(self._analysis_run, state)

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
        self._sync_toolbar_animation_action(False)
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
        full_record = full or _panel_visible(self, "signal_panel")
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
            self._set_app_status(status_text)

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
        self._sync_toolbar_animation_action(False)
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
        if not _panel_visible(self, "lyapunov_panel"):
            return

        if config is None or values is None:
            config, values = self._get_current_config_and_values()
        if config is None:
            self._set_app_status("No attractor selected", error=True)
            return

        self.solver.cancel_lyapunov()
        self._set_app_status("Computing Lyapunov spectrum")
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
                self._set_app_status("Solve failed", error=True)
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
            self._set_app_status(message, error=True)
            if self._solve_needed:
                self._solve_needed = False
                full = self._full_needed
                self._full_needed = False
                self._dispatch_solve(full=full)
            return

        perf_finish(self, solve_token, status="ok", partial=is_partial)

        ui_start = time.perf_counter()

        self._clear_app_status()
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
                _panel_visible(self, "projection_panel")
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
            if _panel_visible(self, "poincare_panel"):
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
            self.toolbar_anim_action,
            self.toolbar_loop_action,
            self.toolbar_point_action,
            self.toolbar_line_action,
            self.toolbar_trail_action,
            self.toolbar_grid_action,
            self.toolbar_orbit_action,
            self.toolbar_hover_action,
            self.toolbar_reset_camera_action,
            self.toolbar_fit_camera_action,
            self.toolbar_auto_fit_camera_action,
            self.toolbar_save_view_action,
            self.animation_traj_action,
            self.animation_particle_flow_action,
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

        if self.auto_fit_camera:
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

        if not _panel_visible(self, "projection_panel"):
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

        if not _panel_visible(self, "projection_panel"):
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
        if not _panel_visible(self, "lyapunov_panel"):
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token)
        self.lyapunov_panel.set_result(lyap, ky_dim, t_hist, lyap_hist)
        self._clear_app_status()

    def _on_lyapunov_failed(self, request_id, message):
        if request_id != self._active_lyapunov_request_id:
            return
        if not _panel_visible(self, "lyapunov_panel"):
            self._cancel_lyapunov_analysis()
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token, status="failed")
        self._set_app_status(f"Lyapunov failed: {message}", error=True)

    def _workspace_docks(self):
        panel = self.jupyter_console_panel
        return [
            panel.script_dock,
            panel.variables_dock,
            panel.files_dock,
            panel.console_dock,
            *panel.plots._docks.values(),
            *panel.views3d._docks.values(),
            *panel.tables._docks.values(),
        ]

    def _open_panel_dock(self, panel_name):
        self._panel_docks[panel_name].reveal()
        self._sync_dock_state()

    def _close_panel_dock(self, panel_name):
        self._panel_docks[panel_name].hide()
        self._sync_dock_state()

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
        self._output_panel_visible = not self.output_dock.isHidden()
        for action, docks in (
            (self.toolbar_left_panel_action, self._left_docks),
            (self.toolbar_right_panel_action, self._right_docks),
        ):
            with QtCore.QSignalBlocker(action):
                action.setChecked(any(not dock.isHidden() for dock in docks))
        self._sync_toolbar_panel_actions()

    def _cancel_lyapunov_analysis(self):
        self.solver.cancel_lyapunov()

        request_id = self._active_lyapunov_request_id
        if request_id is not None:
            token = self._lyapunov_perf_tokens.pop(request_id, None)
            perf_finish(self, token, status="cancelled")
        self._active_lyapunov_request_id = None
        self._clear_app_status()

    def _close_lyapunov_panel(self):
        self._close_panel_dock("lyapunov_panel")

    def _toggle_lyapunov_panel(self):
        if _panel_visible(self, "lyapunov_panel"):
            self._close_panel_dock("lyapunov_panel")
        else:
            self._open_panel_dock("lyapunov_panel")

    def _close_projections(self):
        self._close_panel_dock("projection_panel")

    def _toggle_projections(self):
        if _panel_visible(self, "projection_panel"):
            self._close_panel_dock("projection_panel")
        else:
            self._open_panel_dock("projection_panel")

    def _close_poincare(self):
        self._close_panel_dock("poincare_panel")

    def _toggle_poincare(self):
        if _panel_visible(self, "poincare_panel"):
            self._close_panel_dock("poincare_panel")
        else:
            self._open_panel_dock("poincare_panel")

    def _close_bifurcation(self):
        self._close_panel_dock("bifurcation_panel")

    def _toggle_bifurcation(self):
        if _panel_visible(self, "bifurcation_panel"):
            self._close_panel_dock("bifurcation_panel")
        else:
            self._open_panel_dock("bifurcation_panel")

    def _clear_current_explore_traces(self):
        self.jupyter_console_panel.active_explorer().clear_traces()
        self.jupyter_console_panel.set_explore_visible(True)
        self._sync_explore_actions()

    def _clear_current_explore_sliders(self):
        self.jupyter_console_panel.active_explorer().clear_sliders()
        self.jupyter_console_panel.set_explore_visible(True)
        self._sync_explore_actions()

    def _clear_current_explore(self):
        self.jupyter_console_panel.active_explorer().clear()
        self.jupyter_console_panel.set_explore_visible(True)
        self._sync_explore_actions()

    def _remove_current_explore_trace(self, name):
        try:
            self.jupyter_console_panel.active_explorer().remove_trace(name)
        except KeyError as exc:
            self._set_app_status(str(exc), error=True)

        self._sync_explore_actions()

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
            self._set_app_status(f"Failed to export table: {e}", error=True)
            return

        self._set_app_status(f"Exported table to {target}")

    def show_welcome(self):
        dialog = WelcomeDialog(self, app_settings())
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
            self._set_temporary_app_status("No bundled examples available")

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

    def _save_workspace_shell(self, settings):
        for kind, manager in (
            ("plot", self.jupyter_console_panel.plots),
            ("view3d", self.jupyter_console_panel.views3d),
            ("table", self.jupyter_console_panel.tables),
        ):
            settings.setValue(f"workspace/default_{kind}", manager._default_name)
        kind, name = self.jupyter_console_panel.active_view_key()
        script_path = self.jupyter_console_panel.script_panel.current_script_path()
        settings.setValue("workspace/plots", self.jupyter_console_panel.plots.names())
        settings.setValue(
            "workspace/views3d", self.jupyter_console_panel.views3d.names()
        )
        settings.setValue("workspace/tables", self.jupyter_console_panel.tables.names())
        settings.setValue("workspace/active_kind", kind)
        settings.setValue("workspace/active_name", name)
        settings.setValue(
            "workspace/open_scripts",
            [
                str(path)
                for path in self.jupyter_console_panel.script_panel.open_script_paths()
            ],
        )

        if script_path is not None:
            settings.setValue("workspace/current_script", str(script_path))
        else:
            settings.remove("workspace/current_script")

    def _restore_workspace_shell(self, settings):
        for kind, manager in (
            ("plot", self.jupyter_console_panel.plots),
            ("view3d", self.jupyter_console_panel.views3d),
            ("table", self.jupyter_console_panel.tables),
        ):
            name = settings.value(f"workspace/default_{kind}", manager._default_name)
            manager.rename(manager._default_name, name)
        plot_names = settings.value("workspace/plots", [], type=list)
        view_names = settings.value("workspace/views3d", [], type=list)
        table_names = settings.value("workspace/tables", [], type=list)

        for name in plot_names:
            if name != self.jupyter_console_panel.plots._default_name:
                self.jupyter_console_panel.plots.new(name, activate=False)

        for name in view_names:
            if name != self.jupyter_console_panel.views3d._default_name:
                self.jupyter_console_panel.views3d.new(name, activate=False)

        for name in table_names:
            if name != self.jupyter_console_panel.tables._default_name:
                self.jupyter_console_panel.tables.new(name, activate=False)

        kind = settings.value("workspace/active_kind", "plot")
        name = settings.value("workspace/active_name", "Plot")

        try:
            self.jupyter_console_panel.set_active_workspace_view(
                kind, name, activate=False
            )
            manager = (
                self.jupyter_console_panel.views3d
                if kind == "view3d"
                else self.jupyter_console_panel.plots
            )
            manager.activate(name)
        except (KeyError, ValueError):
            pass

        script_path = settings.value("workspace/current_script")
        open_scripts = settings.value("workspace/open_scripts", [], type=list)

        if not open_scripts and script_path:
            open_scripts = [script_path]

        self.jupyter_console_panel.script_panel.restore_scripts(
            open_scripts, script_path
        )

    def _save_app_layout(self):
        settings = app_settings()
        app = QtWidgets.QApplication.instance()
        settings.setValue(
            "layout/plot_theme", app.property("appTheme") if app else None
        )
        settings.setValue("layout/window_geometry", self.saveGeometry())
        self.dock_layout.save(settings)
        settings.setValue("layout/workspace_mode", self.workspace_mode)
        self._save_workspace_shell(settings)

    def _restore_app_layout(self):
        settings = app_settings()

        theme = settings.value("layout/plot_theme", None)
        if theme not in {"light", "dark"}:
            theme = None

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setProperty("appTheme", theme)

        self._sync_theme_actions(theme)
        self._apply_theme()

        geometry = settings.value("layout/window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._restore_workspace_shell(settings)
        self.dock_layout.restore(settings)
        mode = settings.value("layout/workspace_mode", "system")
        self._set_workspace_mode(mode if mode in {"system", "explore"} else "system")

        self._sync_toolbar_panel_actions()
        self.workspace_controller.sync_views()

    def _reset_session_state(self):
        settings = app_settings()
        settings.remove("layout")
        settings.remove("workspace")
        settings.remove("startup")
        settings.sync()

        self.reset_session_state = True
        self._set_temporary_app_status("Reset session state for next launch")

    def closeEvent(self, a0):
        if not self.jupyter_console_panel.script_panel.confirm_close():
            a0.ignore()
            return

        self.jupyter_console_panel.shutdown_kernel()
        self._set_orbit_mode(False)
        self.scene.animation_controller.stop()
        self.solver.shutdown()

        if not self.reset_session_state:
            self._save_app_layout()

        super().closeEvent(a0)
