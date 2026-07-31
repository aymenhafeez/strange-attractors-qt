import weakref
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .bifurcation_panel import BifurcationPanel
from .control_panel import ControlPanel
from .docking import AreaBoundDock as Dock
from .docking import AreaBoundDockArea as DockArea
from .grid_overlay import DEFAULT_GRID_HALF_SIZE
from .jupyter_console_panel import JupyterConsolePanel
from .lab_panel import LabPanel
from .lab_plot_controller import LabPlotController
from .lyapunov_panel import LyapunovPanel
from .perf import PerfProfiler, perf_finish, perf_start
from .poincare_panel import PoincarePanel
from .presets import (
    PresetError,
    build_preset,
    custom_config_from_preset_data,
    delete_named_preset,
    list_presets,
    load_named_preset,
    preset_metadata,
    save_named_preset,
)
from .process_metrics import ProcessUsageStatus
from .projection_panel import ProjectionPanel
from .registry import ATTRACTORS
from .right_panel import RightPanel
from .session import clear_session, load_session, save_session, session_settings
from .solution_validation import validate_solutions
from .solve_manager import SolveManager
from .style import SCENE_TOOLBAR, SPLITTER_HANDLE_HOVER
from .system import SystemInspector
from .view_manager import ViewManager

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PARTIAL_N = 40000
PROJECTION_UPDATE_INTERVAL_MS = 100
MAIN_VIEW_MARGIN = 4
TOOLBAR_ICON_SIZE = 18
LAB_PLOT_COMBO_WIDTH = 132
PROCESS_STATUS_DEFAULT_VISIBLE = True


def _should_update_projection(now_ms, last_update_ms, interval_ms):
    if last_update_ms is None:
        return True

    return now_ms - last_update_ms >= interval_ms


def _solve_status_text(n_trajectories):
    if n_trajectories == 1:
        return "Solving trajectory"
    return f"Solving {n_trajectories} trajectories"


def _copy_solve_values(values):
    return {str(key): float(value) for key, value in values.items()}


def _parameter_by_name(config):
    return {param.name: param for param in config.params}


def _solve_signature(config, values, n, t_max, trajectory_specs):
    return {
        "attractor": config.name,
        "parameters": _copy_solve_values(values),
        "n": int(n),
        "t_max": float(t_max),
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


def _solution_lengths(solutions):
    return [len(solution) for solution in solutions or []]


def _trajectory_solve_specs(config, trajectories, n, t_max, *, full):
    if not trajectories:
        solve_n = int(n if full else min(n, PARTIAL_N))
        return [
            {
                "ic": [float(coord) for coord in config.initial_conditions],
                "n": solve_n,
                "t_max": float(t_max),
            }
        ]

    specs = []
    for trajectory in trajectories:
        trajectory_n = int(trajectory.get("n", n))
        solve_n = trajectory_n if full else min(trajectory_n, PARTIAL_N)
        specs.append(
            {
                "ic": [float(coord) for coord in trajectory["ic"]],
                "n": solve_n,
                "t_max": float(trajectory.get("t_max", t_max)),
            }
        )

    return specs


def _initial_solve_state():
    return {
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


def _attractor_name_for_config(config):
    if config.name == "Custom":
        return "Custom"

    for name, registered_config in ATTRACTORS.items():
        if registered_config is config:
            return name

    return config.name


def _preset_directory():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return app_data + "/presets"

    return QtCore.QDir.homePath() + "/.strange-attractors/presets"


def _app_data_directory():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return Path(app_data)

    return Path(QtCore.QDir.homePath() + "/.strange-attractors")


def _session_attractor_name(state):
    name = state.get("attractor")
    if name in ATTRACTORS:
        return name
    return next(iter(ATTRACTORS.keys()))


def _panel_visible(window, panel_name):
    dock = window._panel_docks.get(panel_name)
    if dock is not None:
        return dock.container() is not None

    panels = {
        "lyapunov_panel": window.lyapunov_panel,
        "projection_panel": window.projection_panel,
        "poincare_panel": window.poincare_panel,
        "bifurcation_panel": window.bifurcation_panel,
        "jupyter_console_panel": window.jupyter_console_panel,
    }
    return panels[panel_name].isVisible()


def _dock_branch_is_current(dock):
    item = dock
    container = dock.container()
    while container is not None:
        try:
            container_type = container.type()
        except AttributeError:
            container_type = None
        if container_type == "tab":
            try:
                stack = container.stack
            except AttributeError:
                stack = None
            if stack is not None and stack.currentWidget() is not item:
                return False
        item = container
        try:
            container = container.container()
        except AttributeError:
            container = None
    return True


def _has_hidden_lyapunov_panel(window):
    return not _panel_visible(window, "lyapunov_panel")


def _lab_visible(window):
    if window.lab_dock is not None:
        return window.lab_dock.container() is not None

    return _panel_visible(window, "jupyter_console_panel")


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        self._initial_full_solves = 0
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._restoring_view = False
        self._active_solve_request_id = None
        self._active_lyapunov_request_id = None
        self._solve_state = _initial_solve_state()
        self._solve_perf_tokens = {}
        self._lyapunov_perf_tokens = {}
        self._last_projection_update_ms = None
        self._last_lab_preview_update_ms = None
        self._latest_projection_solutions = None
        self._settings = session_settings()
        self._session_state = load_session(self._settings)
        self._session_reset_requested = False
        self._perf = PerfProfiler()
        self._process_status_visible = PROCESS_STATUS_DEFAULT_VISIBLE
        self._app_status_message = ""
        self._app_status_clear_timer = None
        self._panel_docks = {}
        self._panel_dock_titles = {}
        self._panel_dock_defaults = {}
        self._closing_panel_dock = None
        self._closing_lab_dock = False
        self._workspace_tab_stacks = weakref.WeakSet()
        self._jupyter_toolbar_actions = []
        self._left_panel_splitter_size = int(WINDOW_WIDTH * 0.22)
        self._right_panel_splitter_size = int(WINDOW_WIDTH * 0.23)
        self.lab_dock = None
        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = _session_attractor_name(self._session_state)
        self._custom_config = None
        self._preset_directory = _preset_directory()
        self._app_data_directory = _app_data_directory()
        self._scripts_directory = self._app_data_directory / "scripts"
        self._scripts_directory.mkdir(parents=True, exist_ok=True)
        self._lab_live_plots = {}
        self._lab_live_items = {}
        self.lab_plot_controller = LabPlotController(self)
        self.system = SystemInspector(self)

        self.solver = SolveManager(self)
        self.solver.solutions_ready.connect(self._on_solve_result)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)
        self.solver.lyapunov_failed.connect(self._on_lyapunov_failed)

        self.scene = ViewManager(self)
        self.scene.animation_finished.connect(self._on_anim_finished)
        self.scene.animation_segments_data.connect(self._on_animation_segments_data)
        self.scene.projections_data.connect(self._on_projections_data)

        self.controls = ControlPanel()
        self.right_panel = RightPanel()
        self.controls.set_right_panel(self.right_panel)
        self.controls.attractor_changed.connect(self.on_attractor_change)
        self.controls.solve_requested.connect(self._on_controls_solve_requested)
        self.controls.n_changed.connect(self._on_n_changed)
        self.controls.t_max_changed.connect(self._on_t_max_changed)
        self.controls.animation_speed_changed.connect(
            self.scene.animation_controller.set_step
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
        self.poincare_panel.plane_changed.connect(
            self.scene.grid_overlay.set_poincare_plane
        )
        self.poincare_panel.close_requested.connect(self._close_poincare)
        self.poincare_panel.hide()

        self.lyapunov_panel = LyapunovPanel()
        self.lyapunov_panel.compute_requested.connect(self._on_lyapunov_requested)
        self.lyapunov_panel.close_requested.connect(self._close_lyapunov_panel)
        self.lyapunov_panel.hide()

        self.projection_panel = ProjectionPanel()
        self.projection_panel.close_requested.connect(self._close_projections)
        self.projection_panel.hide()

        self.bifurcation_panel = BifurcationPanel()
        self.bifurcation_panel.close_requested.connect(self._close_bifurcation)
        self.bifurcation_panel.hide()

        self.jupyter_console_panel = JupyterConsolePanel(
            self._jupyter_console_namespace, script_dir=self._scripts_directory
        )
        self.jupyter_console_panel.script_panel.status_changed.connect(
            lambda message: self._set_temporary_app_status(message)
        )
        self.jupyter_console_panel.close_requested.connect(self._close_jupyter_console)
        self.lab_panel = LabPanel(self.jupyter_console_panel)
        lab_plots = self.lab_plot_controller
        self.lab_panel.follow_requested.connect(lab_plots._on_lab_follow_requested)
        self.lab_panel.live_trace_remove_requested.connect(
            lab_plots._remove_lab_live_trace
        )
        self.lab_panel.live_plot_clear_requested.connect(lab_plots._remove_lab_follow)
        self.jupyter_console_panel.plots.plots_changed.connect(
            lab_plots._on_lab_plots_changed
        )
        self.jupyter_console_panel.plots.current_changed.connect(
            lambda _name: lab_plots._sync_lab_plots()
        )
        self.lab_panel.set_solve_state(self._solve_state)
        lab_plots._sync_lab_plots()

        self._build_toolbar()
        self._build_status_bar()

        self.workspace_dock_area = DockArea()
        self.viewport_dock = Dock("Viewport", size=(10, 12))
        self.viewport_dock.addWidget(self.scene.container)
        self.workspace_dock_area.addDock(self.viewport_dock)
        self.lab_dock = self._build_lab_dock()
        self.lyapunov_dock = self._build_panel_dock("Lyapunov", self.lyapunov_panel)
        self.poincare_dock = self._build_panel_dock("Poincare", self.poincare_panel)
        self.bifurcation_dock = self._build_panel_dock(
            "Bifurcation",
            self.bifurcation_panel,
        )
        self.projection_dock = self._build_panel_dock(
            "Projection heatmaps",
            self.projection_panel,
        )
        self._panel_docks = {
            "lyapunov_panel": self.lyapunov_dock,
            "poincare_panel": self.poincare_dock,
            "bifurcation_panel": self.bifurcation_dock,
            "projection_panel": self.projection_dock,
        }
        self._panel_dock_titles = {
            "lyapunov_panel": "Lyapunov",
            "poincare_panel": "Poincare",
            "bifurcation_panel": "Bifurcation",
            "projection_panel": "Projection heatmaps",
        }
        self._panel_dock_defaults = {
            "lyapunov_panel": ("top", self.viewport_dock),
            "poincare_panel": ("top", self.viewport_dock),
            "bifurcation_panel": ("bottom", self.viewport_dock),
            "projection_panel": ("bottom", self.viewport_dock),
        }
        self._connect_workspace_dock_signals()

        main_area = QtWidgets.QWidget()
        main_area_layout = QtWidgets.QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(
            0,
            MAIN_VIEW_MARGIN,
            0,
            MAIN_VIEW_MARGIN,
        )
        main_area_layout.addWidget(self.workspace_dock_area)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.controls)
        self.main_splitter.addWidget(main_area)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setSizes(
            [
                int(WINDOW_WIDTH * 0.22),
                int(WINDOW_WIDTH * 0.55),
                int(WINDOW_WIDTH * 0.23),
            ]
        )
        self.main_splitter.setStyleSheet(SPLITTER_HANDLE_HOVER)
        visualiser_page = QtWidgets.QWidget()
        visualiser_layout = QtWidgets.QHBoxLayout(visualiser_page)
        visualiser_layout.setContentsMargins(0, 0, 0, 0)
        visualiser_layout.addWidget(self.main_splitter)
        self.setCentralWidget(visualiser_page)

        self.scene.container.installEventFilter(self)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

        self.scene.grid_overlay.build_grid(DEFAULT_GRID_HALF_SIZE)
        self._refresh_presets()
        self.controls.set_current_attractor(self.current_name)
        self._rebuild_view(self.current_name)
        self._restore_session(self._session_state)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize and obj is self.scene.container:
            self.scene.reposition_overlays()

        return super().eventFilter(obj, event)

    def _on_focus_changed(self, _old, _now):
        self._sync_jupyter_workspace_state()

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
            self.solver.cancel_solve()
            self.solver.cancel_lyapunov()
            self._solve_pending = False
            self._latest_projection_solutions = None
            self.scene.clear_solutions()
            self._clear_data_view()
            self.lyapunov_panel.clear()

    def _rebuild_view_from_config(self, config):
        self.scene.animation_controller.stop()
        self._sync_toolbar_animation_action(False)
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self._restoring_view = True
        try:
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
        self._restoring_view = True
        try:
            if config.name == "Custom":
                self._custom_config = config
                self.current_name = "Custom"
                self.controls.set_current_attractor("Custom")
                self.controls.hide_standard_controls()
            else:
                name = _attractor_name_for_config(config)
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

    def _collect_session_state(self):
        values = self.controls.get_current_values()
        visual_options = self._collect_visual_options()
        custom_data = None
        if self.current_name == "Custom" and self._custom_config is not None:
            try:
                custom_data = build_preset(
                    self._custom_config,
                    values,
                    self.current_n,
                    self.current_t_max,
                )
            except PresetError:
                custom_data = None

        state = {
            "attractor": (
                self.current_name
                if self.current_name in ATTRACTORS or custom_data is not None
                else None
            ),
            "custom": custom_data,
            "values": values,
            "n": int(self.current_n),
            "t_max": int(self.current_t_max),
            "visual_options": visual_options,
            "trajectories": self.controls.trajectory_panel.get_session_state(),
            "panels": self._collect_panel_state(),
            "camera": self.scene.camera_controller.get_camera_state(),
            "selected_preset": self.controls.preset_panel.current_preset_name(),
            "lab_live_plots": self.lab_plot_controller._collect_lab_live_plot_state(),
        }
        dock_layout = self._collect_workspace_dock_layout()
        if dock_layout is not None:
            state["workspace_dock_layout"] = dock_layout
        return state

    def _collect_panel_state(self):
        panels = {
            "projections": _panel_visible(self, "projection_panel"),
            "poincare": _panel_visible(self, "poincare_panel"),
            "bifurcation": _panel_visible(self, "bifurcation_panel"),
            "lyapunov": _panel_visible(self, "lyapunov_panel"),
            "jupyter_console": _lab_visible(self),
        }
        panels["performance_status"] = self._process_status_visible
        return panels

    def _collect_visual_options(self):
        options = self.controls.get_visual_options()
        for key, action in [
            ("point", self.toolbar_point_action),
            ("line", self.toolbar_line_action),
            ("trail", self.toolbar_trail_action),
            ("grid", self.toolbar_grid_action),
            ("orbit", self.toolbar_orbit_action),
            ("loop", self.toolbar_loop_action),
        ]:
            options[key] = action.isChecked()
        options["auto_lyapunov"] = (
            self.lyapunov_panel.isVisible() and self.lyapunov_panel.auto_enabled()
        )
        return options

    def _set_visual_options(self, options):
        self.controls.set_visual_options(options)
        for key, action in [
            ("point", self.toolbar_point_action),
            ("line", self.toolbar_line_action),
            ("trail", self.toolbar_trail_action),
            ("grid", self.toolbar_grid_action),
            ("orbit", self.toolbar_orbit_action),
            ("loop", self.toolbar_loop_action),
        ]:
            if key in options:
                action.setChecked(bool(options[key]))
        if "auto_lyapunov" in options:
            self.lyapunov_panel.set_auto_enabled(bool(options["auto_lyapunov"]))

    def _collect_workspace_dock_layout(self):
        try:
            return self.workspace_dock_area.saveState()
        except (AttributeError, TypeError, ValueError):
            return None

    def _restore_session(self, state):
        if not state or (
            state.get("attractor") not in ATTRACTORS
            and state.get("attractor") != "Custom"
        ):
            return

        if state.get("attractor") == "Custom":
            custom_data = state.get("custom")
            if not isinstance(custom_data, dict):
                return
            try:
                config = custom_config_from_preset_data(custom_data)
            except PresetError:
                return
            self._restoring_view = True
            try:
                self._custom_config = config
                self.current_name = "Custom"
                self.controls.set_current_attractor("Custom")
                self.controls.hide_standard_controls()
                self.scene.animation_controller.stop()
                self._sync_toolbar_animation_action(False)
                self.scene.camera_controller.set_camera(config)
                self.controls.configure(config)
                self.controls.custom_panel.set_from_config(config)
                self.controls.set_current_values(state.get("values", {}))
                self.lyapunov_panel.clear()
                self.controls.trajectory_panel.reset(config)
                self.bifurcation_panel.set_config(
                    config, self.controls.get_current_values()
                )
            finally:
                self._restoring_view = False

        values = state.get("values", {})
        if isinstance(values, dict):
            self.controls.set_current_values(values)

        n = state.get("n")
        t_max = state.get("t_max")
        if n is not None and t_max is not None:
            try:
                self.current_n = int(n)
                self.current_t_max = int(t_max)
            except (TypeError, ValueError):
                pass
            else:
                self.controls.set_time_values(self.current_n, self.current_t_max)
                self.controls.set_traj_tail_max(self.current_n)

        visual_options = state.get("visual_options", {})
        if isinstance(visual_options, dict):
            self._set_visual_options(visual_options)

        trajectory_state = state.get("trajectories")
        if isinstance(trajectory_state, dict):
            config, _ = self._get_current_config_and_values()
            if config is not None:
                restoring_view = self._restoring_view
                self._restoring_view = True
                try:
                    self.controls.trajectory_panel.set_session_state(
                        trajectory_state, config
                    )
                finally:
                    self._restoring_view = restoring_view
                self.scene.trajectory_renderer.set_trajectories(
                    self.controls.trajectory_panel.get_trajectories()
                )

        selected_preset = state.get("selected_preset")
        if selected_preset:
            self._refresh_presets(str(selected_preset))

        panels = state.get("panels", {})
        if isinstance(panels, dict):
            if panels.get("lyapunov"):
                self._toggle_lyapunov_panel()
            if panels.get("projections"):
                self._toggle_projections()
            if panels.get("poincare"):
                self._toggle_poincare()
            if panels.get("bifurcation"):
                self._toggle_bifurcation()
            if panels.get("jupyter_console"):
                self._toggle_jupyter_console()
            if "performance_status" in panels:
                self._set_process_status_visible(
                    bool(panels["performance_status"]),
                )

        dock_layout = state.get("workspace_dock_layout")
        if isinstance(dock_layout, dict):
            self._restore_workspace_dock_layout(dock_layout)

        self.lab_plot_controller._restore_lab_live_plot_state(
            state.get("lab_live_plots")
        )

        self._update_plot()

        camera = state.get("camera")
        if isinstance(camera, dict):
            self.scene.camera_controller.set_camera_state(camera)

    def _refresh_presets(self, selected=None):
        preset_panel = self.controls.preset_panel
        preset_panel.set_saved_presets(list_presets(self._preset_directory), selected)
        self._update_preset_summary(selected or preset_panel.current_preset_name())

    def _build_toolbar(self):
        toolbar = QtWidgets.QToolBar("Scene")
        toolbar.setObjectName("sceneToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QtCore.QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        toolbar.setStyleSheet(SCENE_TOOLBAR)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.scene_toolbar = toolbar

        style_icon = QtWidgets.QStyle.StandardPixmap

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
            self._on_anim_toggled,
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

        reset_action = toolbar.addAction(
            self.style().standardIcon(style_icon.SP_BrowserReload), "Reset"
        )
        reset_action.setToolTip("Reset parameters")
        reset_action.triggered.connect(self.controls.reset_to_defaults)

        reset_camera_action = toolbar.addAction(
            QtGui.QIcon.fromTheme("zoom-original"),
            "Reset camera",
            self._reset_camera,
        )
        reset_camera_action.setToolTip("Reset camera")

        fit_camera_action = toolbar.addAction(
            QtGui.QIcon.fromTheme("view-fullscreen"),
            "Fit",
            self._fit_camera_to_solutions,
        )
        fit_camera_action.setToolTip("Fit view to trajectories")

        save_action = toolbar.addAction(
            self.style().standardIcon(style_icon.SP_DialogSaveButton),
            "Save",
            self.scene.viewport_overlay.save_view_as_png,
        )
        save_action.setToolTip("Save view as PNG")

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
            self.scene.camera_controller.set_orbit_mode,
            "Orbit camera automatically",
            icon=self._toolbar_icon(
                "object-rotate-right",
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
            ),
        )

        toolbar.addSeparator()

        solve_action = toolbar.addAction(
            self._toolbar_icon(
                "system-run",
                QtWidgets.QStyle.StandardPixmap.SP_MediaPlay,
            ),
            "Solve",
        )
        solve_action.setToolTip("Run a full solve")
        solve_action.triggered.connect(lambda: self._on_controls_solve_requested(True))

        self.tools_button = QtWidgets.QToolButton()
        self.tools_button.setText("Tools")
        self.tools_button.setToolTip("Open analysis and maintenance tools")
        self.tools_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        tools_menu = QtWidgets.QMenu(self.tools_button)
        self.toolbar_lyapunov_action = self._add_panel_menu_action(
            tools_menu,
            "Lyapunov spectrum",
            self._toggle_lyapunov_panel,
        )
        self.toolbar_projection_action = self._add_panel_menu_action(
            tools_menu,
            "Projection heatmaps",
            self._toggle_projections,
        )
        self.toolbar_poincare_action = self._add_panel_menu_action(
            tools_menu,
            "Poincare section",
            self._toggle_poincare,
        )
        self.toolbar_bifurcation_action = self._add_panel_menu_action(
            tools_menu,
            "Bifurcation diagram",
            self._toggle_bifurcation,
        )
        self.toolbar_jupyter_console_action = self._add_panel_menu_action(
            tools_menu,
            "Console",
            self._toggle_jupyter_console,
        )
        self.toolbar_process_status_action = self._add_panel_menu_action(
            tools_menu,
            "Status bar",
            lambda: self._toggle_process_status(),
        )
        tools_menu.addSeparator()
        open_folder_action = tools_menu.addAction("Open preset folder")
        open_folder_action.triggered.connect(self._open_preset_folder)
        reset_session_action = tools_menu.addAction("Reset saved session")
        reset_session_action.triggered.connect(self._reset_saved_session)
        self.tools_button.setMenu(tools_menu)
        toolbar.addWidget(self.tools_button)

        toolbar.addSeparator()
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        self._build_jupyter_toolbar_actions(toolbar)
        self.toolbar_right_panel_action = self._add_checked_icon_toolbar_action(
            toolbar,
            self._side_panel_icon("right"),
            True,
            lambda checked: self._set_right_panel_visible(checked),
            "Show right panel",
        )

        self._sync_toolbar_panel_actions()

    def _build_status_bar(self):
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

    def _side_panel_icon(self, side):
        icon = QtGui.QIcon.fromTheme(f"sidebar-show-{side}")
        if icon.isNull():
            icon = self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
            )
        return icon

    def _set_left_panel_visible(self, checked):
        if checked:
            self.controls.show()
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 3 and sizes[0] == 0:
                sizes[0] = self._left_panel_splitter_size
                self.main_splitter.setSizes(sizes)
            return

        sizes = self.main_splitter.sizes()
        if len(sizes) >= 3 and sizes[0] > 0:
            self._left_panel_splitter_size = sizes[0]
        self.controls.hide()

    def _set_trail_mode(self, checked):
        self.scene.trajectory_renderer.set_trail_mode(checked)
        self.controls.set_trail_options_visible(checked)

    def _set_line_mode(self, checked):
        mode = "line" if checked else "points"
        self.controls.trajectory_panel.set_render_mode_all(mode)
        self.scene.trajectory_renderer.set_line_mode(checked)

    def _set_right_panel_visible(self, checked):
        if checked:
            self.right_panel.show()
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 3 and sizes[2] == 0:
                sizes[2] = self._right_panel_splitter_size
                self.main_splitter.setSizes(sizes)
            return

        sizes = self.main_splitter.sizes()
        if len(sizes) >= 3 and sizes[2] > 0:
            self._right_panel_splitter_size = sizes[2]
        self.right_panel.hide()

    def _build_panel_dock(self, title, panel):
        dock = Dock(title, size=(10, 4), closable=True)
        dock.addWidget(panel)
        dock.sigClosed.connect(lambda _dock: self._on_panel_dock_closed(panel))
        return dock

    def _build_lab_dock(self):
        dock = Dock("Console", size=(10, 12), closable=True)
        dock.addWidget(self.lab_panel)
        dock.sigClosed.connect(lambda _dock: self._on_lab_dock_closed())

        return dock

    def _add_panel_menu_action(self, menu, text, callback):
        action = menu.addAction(text)
        action.setCheckable(True)
        action.triggered.connect(lambda: callback())
        return action

    def _sync_toolbar_panel_actions(self):
        with (
            QtCore.QSignalBlocker(self.toolbar_lyapunov_action),
            QtCore.QSignalBlocker(self.toolbar_projection_action),
            QtCore.QSignalBlocker(self.toolbar_poincare_action),
            QtCore.QSignalBlocker(self.toolbar_bifurcation_action),
            QtCore.QSignalBlocker(self.toolbar_jupyter_console_action),
            QtCore.QSignalBlocker(self.toolbar_process_status_action),
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
            self.toolbar_jupyter_console_action.setChecked(_lab_visible(self))
            self.toolbar_process_status_action.setChecked(self._process_status_visible)
        self._sync_jupyter_workspace_state()

    def _set_process_status_visible(self, visible):
        self._process_status_visible = bool(visible)

        self.process_status.setVisible(self._process_status_visible)
        self.process_status.set_active(self._process_status_visible)
        self.statusBar().setVisible(self._process_status_visible)

        if self.toolbar_process_status_action.isChecked() != self._process_status_visible:
            with QtCore.QSignalBlocker(self.toolbar_process_status_action):
                self.toolbar_process_status_action.setChecked(
                    self._process_status_visible
                )

        self._sync_status_bar_visibility()

    def _toggle_process_status(self):
        self._set_process_status_visible(not self._process_status_visible)

    def _set_app_status(self, message, error=False):
        self._app_status_message = str(message)
        colour = "#ff6b6b" if error else "#178640"
        self.app_status_label.setText(self._app_status_message)
        self.app_status_label.setStyleSheet(
            f"border: none; padding: 0 4px 3px 4px; font-size: 12px; color: {colour};"
        )

        self._sync_status_bar_visibility()

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
        self.app_status_label.clear()

        self._sync_status_bar_visibility()

    def _sync_status_bar_visibility(self):
        self.statusBar().setVisible(
            bool(self._process_status_visible or self._app_status_message)
        )

    def _build_jupyter_toolbar_actions(self, toolbar):
        self._jupyter_toolbar_actions = []
        toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        plot_item = self.jupyter_console_panel.plot_widget.getPlotItem()
        view_box = plot_item.getViewBox()

        view_all_action = toolbar.addAction(
            self._toolbar_icon(
                "zoom-fit-best",
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton,
            ),
            "View all",
        )
        view_all_action.setToolTip("Fit all plot data")
        view_all_action.triggered.connect(view_box.autoRange)
        self._jupyter_toolbar_actions.append(view_all_action)
        self._keep_toolbar_action_from_taking_focus(toolbar, view_all_action)

        mouse_group = QtGui.QActionGroup(toolbar)
        mouse_group.setExclusive(True)
        pan_action = toolbar.addAction(
            self._toolbar_icon(
                "transform-move",
                QtWidgets.QStyle.StandardPixmap.SP_ArrowUp,
            ),
            "Pan",
        )
        pan_action.setCheckable(True)
        pan_action.setChecked(True)
        pan_action.setToolTip("Pan with left mouse button")
        zoom_action = toolbar.addAction(
            self._toolbar_icon(
                "zoom-in",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
            ),
            "Zoom",
        )
        zoom_action.setCheckable(True)
        zoom_action.setToolTip("Zoom to rectangle with left mouse button")
        mouse_group.addAction(pan_action)
        mouse_group.addAction(zoom_action)
        pan_action.triggered.connect(lambda: view_box.setLeftButtonAction("pan"))
        zoom_action.triggered.connect(lambda: view_box.setLeftButtonAction("rect"))
        self._jupyter_toolbar_actions.extend([pan_action, zoom_action])
        self._keep_toolbar_action_from_taking_focus(toolbar, pan_action)
        self._keep_toolbar_action_from_taking_focus(toolbar, zoom_action)

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        for text, widget in [
            ("X grid", plot_item.ctrl.xGridCheck),
            ("Y grid", plot_item.ctrl.yGridCheck),
        ]:
            self._jupyter_toolbar_actions.append(
                self._add_plot_option_action(toolbar, text, widget)
            )

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        self._add_jupyter_plot_controls(toolbar)
        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        self._jupyter_toolbar_actions.append(
            self._add_toolbar_menu_button(
                toolbar, "Plot", plot_item.getMenu(), "Plot options"
            )
        )
        view_menu = view_box.menu
        if view_menu is not None:
            self._jupyter_toolbar_actions.append(
                self._add_toolbar_menu_button(
                    toolbar, "View", view_menu, "ViewBox options"
                )
            )

        for action in self._jupyter_toolbar_actions:
            action.setVisible(False)

    def _add_jupyter_plot_controls(self, toolbar):
        label = QtWidgets.QLabel("Plot")
        label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._jupyter_toolbar_actions.append(toolbar.addWidget(label))

        self.toolbar_lab_plot_combo = QtWidgets.QComboBox()
        self.toolbar_lab_plot_combo.setFixedWidth(LAB_PLOT_COMBO_WIDTH)
        self.toolbar_lab_plot_combo.currentIndexChanged.connect(
            lambda _index: self.lab_plot_controller._on_toolbar_lab_plot_selected()
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_lab_plot_combo)
        )

        self.toolbar_lab_plot_name = QtWidgets.QLineEdit()
        self.toolbar_lab_plot_name.setPlaceholderText("Plot name")
        self.toolbar_lab_plot_name.setMaximumWidth(130)
        self.toolbar_lab_plot_name.returnPressed.connect(
            lambda: self._rename_current_lab_plot()
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_lab_plot_name)
        )

        icon_specs = [
            (
                "New",
                "list-add",
                QtWidgets.QStyle.StandardPixmap.SP_FileIcon,
                lambda: self._new_lab_plot(),
                "Create a new console plot",
            ),
            (
                "Rename",
                "edit-rename",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                lambda: self._rename_current_lab_plot(),
                "Rename the current console plot",
            ),
            (
                "Clear",
                "edit-clear-history",
                QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton,
                lambda: self.lab_plot_controller._clear_lab_plot(),
                "Clear the current console plot",
            ),
            (
                "Clear all",
                "edit-delete",
                QtWidgets.QStyle.StandardPixmap.SP_TrashIcon,
                lambda: self.lab_plot_controller._clear_all_lab_plots(),
                "Clear all console plots",
            ),
        ]
        for text, theme_name, fallback_icon, callback, tooltip in icon_specs:
            action = toolbar.addAction(
                self._toolbar_icon(theme_name, fallback_icon),
                text,
            )
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            self._jupyter_toolbar_actions.append(action)
            self._keep_toolbar_action_from_taking_focus(toolbar, action)
        self.lab_plot_controller._sync_lab_plots()

    def _toolbar_icon(self, theme_name, fallback_icon):
        icon = QtGui.QIcon.fromTheme(theme_name)
        if icon.isNull():
            icon = self.style().standardIcon(fallback_icon)
        return icon

    def _keep_toolbar_action_from_taking_focus(self, toolbar, action):
        widget = toolbar.widgetForAction(action)
        if widget is not None:
            widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def _add_plot_option_action(self, toolbar, text, widget):
        action = toolbar.addAction(text)
        action.setCheckable(True)
        action.setChecked(widget.isChecked())
        action.toggled.connect(widget.setChecked)
        widget.toggled.connect(action.setChecked)
        self._keep_toolbar_action_from_taking_focus(toolbar, action)
        return action

    def _add_toolbar_menu_button(self, toolbar, text, menu, tooltip=None):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        return toolbar.addWidget(button)

    def _sync_jupyter_toolbar_visibility(self):
        if self.lab_dock is not None:
            visible = (
                self.lab_dock.container() is not None
                and _dock_branch_is_current(self.lab_dock)
            )
        else:
            visible = _lab_visible(self)

        for action in self._jupyter_toolbar_actions:
            action.setVisible(visible)

    def _sync_jupyter_workspace_state(self):
        self._watch_workspace_tab_stacks()
        self._sync_jupyter_toolbar_visibility()

    def _sync_toolbar_animation_action(self, playing):
        style_icon = QtWidgets.QStyle.StandardPixmap
        if playing:
            self.toolbar_anim_action.setIcon(
                self.style().standardIcon(style_icon.SP_MediaStop)
            )
            self.toolbar_anim_action.setText("Stop")
            self.toolbar_anim_action.setToolTip("Stop animation")
        else:
            self.toolbar_anim_action.setIcon(
                self.style().standardIcon(style_icon.SP_MediaPlay)
            )
            self.toolbar_anim_action.setText("Play")
            self.toolbar_anim_action.setToolTip("Play animation")

    def _open_preset_folder(self):
        Path(self._preset_directory).mkdir(parents=True, exist_ok=True)
        opened = QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(self._preset_directory)
        )
        if not opened:
            self._set_app_status("Could not open preset folder", error=True)

    def _reset_saved_session(self):
        clear_session(self._settings)
        self._session_reset_requested = True
        self._set_app_status("Saved session reset")

    def _save_session_on_close(self):
        if not self._session_reset_requested:
            save_session(self._settings, self._collect_session_state())

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

    def _default_preset_name(self):
        return f"{self.current_name} preset"

    def _save_preset(self, name, notes):
        config, values = self._get_current_config_and_values()
        if config is None:
            self._set_app_status("No attractor selected", error=True)
            return

        preset_name = name.strip() or self._default_preset_name()

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
            "system": self.system,
            "console_plot": plot,
            "console_plots": self.jupyter_console_panel.plots,
            "clear_plot": plot.clear,
            "current_values": lambda: self.system.values,
            "scripts_dir": self._scripts_directory,
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

        return self.system.parameters()

    def _set_console_time(self, *, n=None, t_max=None, solve=False):
        next_n = self.current_n if n is None else self._validated_console_n(n)
        next_t_max = (
            self.current_t_max
            if t_max is None
            else self._validated_console_t_max(t_max)
        )
        self.current_n = next_n
        self.current_t_max = next_t_max
        self.controls.set_time_values(self.current_n, self.current_t_max)
        self.controls.set_traj_tail_max(self.current_n)

        if solve:
            self._on_controls_solve_requested(True)

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

        params = _parameter_by_name(config)
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

    def _set_solve_state(self, **updates):
        state = dict(self._solve_state)
        state.update(updates)
        self._solve_state = state
        self.lab_panel.set_solve_state(state)
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
        user_n = self.current_n or config.time_defaults.n
        t_max = self.current_t_max
        trajectories = self.controls.trajectory_panel.get_trajectories()
        trajectory_specs = _trajectory_solve_specs(
            config,
            trajectories,
            user_n,
            t_max,
            full=full,
        )
        dispatch_n = max(spec["n"] for spec in trajectory_specs)
        dispatch_t_max = max(spec["t_max"] for spec in trajectory_specs)
        self.solver.cancel_lyapunov()
        if full:
            self._set_app_status(_solve_status_text(len(trajectory_specs)))
        self._active_solve_request_id = self.solver.request_solve(
            config, values, trajectory_specs, dispatch_n, not full, dispatch_t_max
        )
        signature = _solve_signature(
            config,
            values,
            dispatch_n,
            dispatch_t_max,
            trajectory_specs,
        )
        self._set_solve_state(
            solving=True,
            valid=False,
            stale=bool(self.scene.trajectory_renderer.solutions),
            partial=not full,
            last_error=None,
            request_id=self._active_solve_request_id,
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
            "solve",
            key=self._active_solve_request_id,
            attractor=config.name,
            full=full,
            partial=not full,
            n=dispatch_n,
            t_max=dispatch_t_max,
            trajectories=len(trajectory_specs),
        )
        if token is not None:
            self._solve_perf_tokens[self._active_solve_request_id] = token

    def _on_controls_solve_requested(self, full):
        self.scene.animation_controller.stop()
        self._sync_toolbar_animation_action(False)
        if (
            not full
            and self._solve_pending
            and self._solve_state.get("partial", False)
        ):
            self._solve_needed = True
            self._full_needed = False

            return

        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = full
        self._full_needed = full
        self._dispatch_solve(full=full)

    def _auto_lyapunov_enabled(self):
        return self.lyapunov_panel.isVisible() and self.lyapunov_panel.auto_enabled()

    def _request_lyapunov(self, config=None, values=None):
        if _has_hidden_lyapunov_panel(self):
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

    def _on_lyapunov_requested(self):
        self._request_lyapunov()

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
                stale=bool(self.scene.trajectory_renderer.solutions),
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

        is_valid, message = validate_solutions(solutions)
        if not is_valid:
            perf_finish(self, solve_token, status="invalid", partial=is_partial)
            self._set_solve_state(
                solving=False,
                valid=False,
                stale=bool(self.scene.trajectory_renderer.solutions),
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
        self._clear_app_status()
        self.scene.trajectory_renderer.display_solutions(solutions, is_partial)
        self._update_data_view(solutions, is_partial)
        self._set_solve_state(
            solving=False,
            valid=not is_partial,
            stale=is_partial or bool(self._solve_needed),
            partial=is_partial,
            last_error=None,
            solution_points=_solution_lengths(solutions),
        )

        if is_partial:
            self.lab_plot_controller._refresh_lab_live_preview(solutions)

        if not is_partial:
            self._last_lab_preview_update_ms = None
            self._latest_projection_solutions = solutions
            config, values = self._get_current_config_and_values()
            if config is not None:
                if _panel_visible(self, "poincare_panel"):
                    self.poincare_panel.set_attractor(config, values)
                if self._auto_lyapunov_enabled():
                    self._request_lyapunov(config, values)
            self._update_projection_panel_from_solutions(solutions)
            if (
                _panel_visible(self, "projection_panel")
                and self._initial_full_solves == 0
            ):
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1
            self.scene.grid_overlay.auto_adjust_grid(solutions)
            self.lab_plot_controller._refresh_lab_live_plots()

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

    def _reapply_projections(self):
        solutions = (
            self._latest_projection_solutions
            or self.scene.trajectory_renderer.solutions
        )
        self.projection_panel.reapply_projections(solutions)

    def _update_projection_panel_from_solutions(self, solutions):
        if not _panel_visible(self, "projection_panel"):
            return

        all_sol = np.concatenate(solutions, axis=0)
        x, y, z = all_sol.T
        token = perf_start(
            self,
            "projection_update",
            source="solve_result",
            points=len(all_sol),
        )
        self.projection_panel.update_projections(x, y, z)
        perf_finish(self, token)
        self._last_projection_update_ms = QtCore.QDateTime.currentMSecsSinceEpoch()

    def _on_projections_data(self, x, y, z):
        if not _panel_visible(self, "projection_panel"):
            return

        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        if not _should_update_projection(
            now_ms,
            self._last_projection_update_ms,
            PROJECTION_UPDATE_INTERVAL_MS,
        ):
            return

        self._last_projection_update_ms = now_ms
        token = perf_start(
            self,
            "projection_update",
            source="animation",
            points=len(x),
        )
        self.projection_panel.update_projections(x, y, z)
        perf_finish(self, token)

    def _on_animation_segments_data(self, segments):
        self.lab_plot_controller._refresh_lab_live_preview(
            segments, kinds={"projection"}
        )

    def _reset_camera(self):
        config, _ = self._get_current_config_and_values()
        if config is not None:
            self.scene.camera_controller.set_camera(config)

    def _fit_camera_to_solutions(self):
        self.scene.camera_controller.fit_camera_to_solutions(
            self.scene.trajectory_renderer.solutions
        )

    def _on_anim_toggled(self):
        playing = self.scene.animation_controller.toggle()
        self._sync_toolbar_animation_action(playing)

    def _on_anim_finished(self):
        self._sync_toolbar_animation_action(False)

    def _on_n_changed(self, val):
        self.current_n = val
        self.controls.set_traj_tail_max(val)

    def _on_t_max_changed(self, val):
        self.current_t_max = val

    def _on_trajectories_changed(self, trajectories):
        self.scene.trajectory_renderer.set_trajectories(trajectories)
        if self._restoring_view:
            return

        self._latest_projection_solutions = None
        self.scene.clear_solutions()
        self._clear_data_view()
        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _on_trajectory_styles_changed(self, trajectories):
        renderer = self.scene.trajectory_renderer
        renderer.set_trajectories(trajectories)
        renderer.refresh_colours()

    def _on_lyapunov_result(self, request_id, lyap, ky_dim, t_hist, lyap_hist):
        if request_id != self._active_lyapunov_request_id:
            return
        if _has_hidden_lyapunov_panel(self):
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token)
        self.lyapunov_panel.set_result(lyap, ky_dim, t_hist, lyap_hist)
        self._clear_app_status()

    def _on_lyapunov_failed(self, request_id, message):
        if request_id != self._active_lyapunov_request_id:
            return
        if _has_hidden_lyapunov_panel(self):
            self._cancel_lyapunov_analysis()
            return

        token = self._lyapunov_perf_tokens.pop(request_id, None)
        perf_finish(self, token, status="failed")
        self._set_app_status(f"Lyapunov failed: {message}", error=True)

    def _panel_dock_for(self, panel):
        for dock in self._panel_docks.values():
            if panel in dock.widgets:
                return dock
        return None

    def _connect_workspace_dock_signals(self):
        docks = [self.viewport_dock, self.lab_dock]
        docks.extend(self._panel_docks.values())
        for dock in docks:
            if dock is None:
                continue
            dock.container_changed.connect(self._on_workspace_layout_changed)

    def _on_workspace_layout_changed(self):
        QtCore.QTimer.singleShot(0, self._sync_jupyter_workspace_state)

    def _watch_workspace_tab_stacks(self):
        try:
            containers, _docks = self.workspace_dock_area.findAll()
        except (AttributeError, RuntimeError):
            return

        for container in containers:
            try:
                stack = container.stack
            except AttributeError:
                stack = None
            if stack is None or stack in self._workspace_tab_stacks:
                continue
            stack.currentChanged.connect(
                lambda _index: self._sync_jupyter_workspace_state()
            )
            self._workspace_tab_stacks.add(stack)

    def _restore_workspace_dock_layout(self, dock_layout):
        try:
            self.workspace_dock_area.restoreState(
                dock_layout,
                missing="ignore",
                extra="bottom",
            )
        except Exception:  # noqa: BLE001
            return
        self._sync_jupyter_workspace_state()

    def _replace_closed_lab_dock(self):
        dock = self._build_lab_dock()
        dock.container_changed.connect(self._on_workspace_layout_changed)
        self.lab_dock = dock

    def _open_lab_dock(self):
        if self.lab_dock is None:
            self.lab_panel.show()
            return

        if self.lab_dock.container() is None:
            self.workspace_dock_area.addDock(
                self.lab_dock,
                position="above",
                relativeTo=self.viewport_dock,
            )
        self.lab_panel.show()
        if self.lab_dock.container() is not None:
            try:
                self.lab_dock.raiseDock()
            except AttributeError:
                pass
        self._sync_jupyter_workspace_state()

    def _panel_name_for_panel(self, panel):
        for panel_name, dock in self._panel_docks.items():
            if panel in dock.widgets:
                return panel_name
        return None

    def _replace_closed_panel_dock(self, panel_name, panel):
        title = self._panel_dock_titles.get(panel_name)
        if title is None:
            return

        dock = self._build_panel_dock(title, panel)
        dock.container_changed.connect(self._on_workspace_layout_changed)
        self._panel_docks[panel_name] = dock

    def _open_panel_dock(self, panel, panel_name):
        dock = self._panel_docks.get(panel_name)
        if dock is None:
            panel.show()
            return

        if dock.container() is None:
            position, relative_to = self._panel_dock_defaults[panel_name]
            self.workspace_dock_area.addDock(
                dock,
                position=position,
                relativeTo=relative_to,
            )
        panel.show()
        if dock.container() is not None:
            try:
                dock.raiseDock()
            except AttributeError:
                pass
        self._sync_jupyter_workspace_state()

    def _close_panel_dock(self, panel):
        dock = self._panel_dock_for(panel)
        if dock is None:
            return 0

        if dock.container() is not None and self._closing_panel_dock is not dock:
            self._closing_panel_dock = dock
            try:
                dock.close()
            finally:
                self._closing_panel_dock = None
        return 0

    def _on_panel_dock_closed(self, panel):
        panel_name = self._panel_name_for_panel(panel)
        dock = self._panel_dock_for(panel)
        if self._closing_panel_dock is dock:
            if panel_name is not None:
                self._replace_closed_panel_dock(panel_name, panel)
            return

        if panel is self.lyapunov_panel:
            self._close_lyapunov_panel()
        elif panel is self.projection_panel:
            self._close_projections()
        elif panel is self.poincare_panel:
            self._close_poincare()
        elif panel is self.bifurcation_panel:
            self._close_bifurcation()

        if panel_name is not None:
            self._replace_closed_panel_dock(panel_name, panel)

    def _cancel_lyapunov_analysis(self):
        self.solver.cancel_lyapunov()

        request_id = self._active_lyapunov_request_id
        if request_id is not None:
            token = self._lyapunov_perf_tokens.pop(request_id, None)
            perf_finish(self, token, status="cancelled")
        self._active_lyapunov_request_id = None
        self._clear_app_status()

    def _close_lyapunov_panel(self):
        self._cancel_lyapunov_analysis()
        self.lyapunov_panel.hide()
        size = self._close_panel_dock(self.lyapunov_panel)
        if size > 0:
            self._lyapunov_splitter_size = size
        self._sync_toolbar_panel_actions()

    def _toggle_lyapunov_panel(self):
        if _panel_visible(self, "lyapunov_panel"):
            self._close_lyapunov_panel()
        else:
            self._open_panel_dock(self.lyapunov_panel, "lyapunov_panel")
            if self.lyapunov_panel.auto_enabled():
                self._request_lyapunov()
            self._sync_toolbar_panel_actions()

    def _close_projections(self):
        self.projection_panel.hide()
        size = self._close_panel_dock(self.projection_panel)
        if size > 0:
            self._projection_splitter_size = size
        self._sync_toolbar_panel_actions()

    def _toggle_projections(self):
        if _panel_visible(self, "projection_panel"):
            self._close_projections()
        else:
            self._open_panel_dock(self.projection_panel, "projection_panel")
            QtCore.QTimer.singleShot(0, self._reapply_projections)
            QtCore.QTimer.singleShot(50, self._reapply_projections)
            self._sync_toolbar_panel_actions()

    def _close_poincare(self):
        self.poincare_panel.cancel_solve()
        self.scene.grid_overlay.remove_poincare_plane()
        self.poincare_panel.hide()
        size = self._close_panel_dock(self.poincare_panel)
        if size > 0:
            self._poincare_splitter_size = size
        self._sync_toolbar_panel_actions()

    def _toggle_poincare(self):
        if _panel_visible(self, "poincare_panel"):
            self._close_poincare()
        else:
            self._open_panel_dock(self.poincare_panel, "poincare_panel")
            self.scene.grid_overlay.set_poincare_plane(
                self.poincare_panel.plane_combo.currentText(),
                self.poincare_panel.value_spin.value(),
            )
            self.poincare_panel.recompute()
            config, values = self._get_current_config_and_values()
            if config is not None:
                self.poincare_panel.set_attractor(config, values)
            self._sync_toolbar_panel_actions()

    def _close_bifurcation(self):
        self.bifurcation_panel.cancel_sweep()
        self.bifurcation_panel.hide()
        size = self._close_panel_dock(self.bifurcation_panel)
        if size > 0:
            self._bifurcation_splitter_size = size
        self._sync_toolbar_panel_actions()

    def _toggle_bifurcation(self):
        if _panel_visible(self, "bifurcation_panel"):
            self._close_bifurcation()
        else:
            config, values = self._get_current_config_and_values()
            if config is None:
                return
            self.bifurcation_panel.set_config(config, values)
            self._open_panel_dock(
                self.bifurcation_panel,
                "bifurcation_panel",
            )
            self._sync_toolbar_panel_actions()

    def _new_lab_plot(self):
        self.jupyter_console_panel.plots.new()
        self._sync_jupyter_workspace_state()

    def _rename_current_lab_plot(self):
        old_name = self.jupyter_console_panel.plots.current_name
        new_name = self.toolbar_lab_plot_name.text().strip()
        if new_name:
            self.lab_plot_controller._rename_lab_plot(old_name, new_name)

    def _on_lab_dock_closed(self):
        if not self._closing_lab_dock:
            self.lab_panel.hide()
        self._replace_closed_lab_dock()
        self._sync_jupyter_workspace_state()
        self._sync_toolbar_panel_actions()

    def _close_jupyter_console(self):
        if self.lab_dock is not None and self.lab_dock.container() is not None:
            self._closing_lab_dock = True
            try:
                self.lab_dock.close()
            finally:
                self._closing_lab_dock = False
        self.lab_panel.hide()
        self._sync_jupyter_workspace_state()
        self._sync_toolbar_panel_actions()

    def _toggle_jupyter_console(self):
        if _lab_visible(self):
            self._close_jupyter_console()
        else:
            self.jupyter_console_panel.ensure_console()
            self._open_lab_dock()
            self.jupyter_console_panel.focus_console()
            self._sync_jupyter_workspace_state()
            self._sync_toolbar_panel_actions()

    def closeEvent(self, a0):
        self._save_session_on_close()
        self.jupyter_console_panel.shutdown_kernel()
        self.scene.camera_controller.set_orbit_mode(False)
        self.scene.animation_controller.stop()
        self.solver.shutdown()
        super().closeEvent(a0)
