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
from .system import PLOT_MODE_REPLACE, SystemInspector
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


def _has_console_solutions(window):
    scene = getattr(window, "scene", None)
    if scene is None or not hasattr(scene, "get_solutions"):
        return False

    return bool(scene.get_solutions())


def _set_solve_state(window, **updates):
    state = dict(getattr(window, "_solve_state", {}))
    state.update(updates)
    window._solve_state = state
    lab_panel = getattr(window, "lab_panel", None)

    if lab_panel is not None:
        lab_panel.set_solve_state(state)

    return state


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

    return str(QtCore.QDir.homePath() + "/.strange-attractors/presets")


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


def _can_restore_builtin_session(state):
    return state.get("attractor") in ATTRACTORS


def _can_restore_session(state):
    return _can_restore_builtin_session(state) or state.get("attractor") == "Custom"


def _sync_panel_toolbar(window):
    sync = getattr(window, "_sync_toolbar_panel_actions", None)
    if sync is not None:
        sync()


def _sync_animation_toolbar(window, playing):
    sync = getattr(window, "_sync_toolbar_animation_action", None)
    if sync is not None:
        sync(playing)


def _lyapunov_auto_enabled(window):
    panel = getattr(window, "lyapunov_panel", None)
    if panel is not None:
        return panel.isVisible() and panel.auto_enabled()

    auto_lyapunov_enabled = getattr(window.controls, "auto_lyapunov_enabled", None)
    if auto_lyapunov_enabled is None:
        return True

    return auto_lyapunov_enabled()


def _set_lyapunov_auto_enabled(window, enabled):
    panel = getattr(window, "lyapunov_panel", None)
    if panel is not None:
        panel.set_auto_enabled(enabled)


def _clear_lyapunov_display(window):
    panel = getattr(window, "lyapunov_panel", None)
    if panel is not None:
        panel.clear()
        return

    clear = getattr(window.scene, "clear_lyapunov", None)
    if clear is not None:
        clear()


def _set_lyapunov_display(window, lyap, ky_dim, t_hist, lyap_hist):
    panel = getattr(window, "lyapunov_panel", None)
    if panel is not None:
        panel.set_result(lyap, ky_dim, t_hist, lyap_hist)
        return

    set_result = getattr(window.scene, "set_lyapunov_result", None)
    if set_result is not None:
        set_result(lyap, ky_dim, t_hist, lyap_hist)


def _panel_visible(window, panel_name):
    panel_docks = getattr(window, "_panel_docks", {})
    dock = panel_docks.get(panel_name)
    if dock is not None:
        return dock.container() is not None

    panel = getattr(window, panel_name, None)
    return bool(panel is not None and panel.isVisible())


def _dock_branch_is_current(dock):
    item = dock
    container = dock.container()
    while container is not None:
        container_type = getattr(container, "type", lambda: None)()
        if container_type == "tab":
            stack = getattr(container, "stack", None)
            if stack is not None and stack.currentWidget() is not item:
                return False
        item = container
        container = container.container() if hasattr(container, "container") else None
    return True


def _panel_visible_to_user(window, panel_name):
    panel_docks = getattr(window, "_panel_docks", {})
    dock = panel_docks.get(panel_name)
    if dock is not None:
        return dock.container() is not None and _dock_branch_is_current(dock)

    return _panel_visible(window, panel_name)


def _has_hidden_lyapunov_panel(window):
    panel = getattr(window, "lyapunov_panel", None)
    return bool(panel is not None and not _panel_visible(window, "lyapunov_panel"))


def _lab_visible(window):
    dock = getattr(window, "lab_dock", None)
    if dock is not None:
        return dock.container() is not None

    return _panel_visible(window, "jupyter_console_panel")


def _lab_visible_to_user(window):
    dock = getattr(window, "lab_dock", None)
    if dock is not None:
        return dock.container() is not None and _dock_branch_is_current(dock)

    return _lab_visible(window)


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
        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = _session_attractor_name(self._session_state)
        self._custom_config = None
        self._preset_directory = _preset_directory()
        self._app_data_directory = _app_data_directory()
        self._scripts_directory = self._app_data_directory / "scripts"
        self._scripts_directory.mkdir(parents=True, exist_ok=True)
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
        self.controls.animation_speed_changed.connect(self.scene.set_anim_step)
        self.controls.orbit_speed_changed.connect(self.scene.set_orbit_speed)
        self.controls.alpha_slider.valueChanged.connect(self.scene.set_alpha)
        self.controls.alpha_spin.valueChanged.connect(self.scene.set_alpha)
        self.right_panel.preset_panel.preset_save_requested.connect(self._save_preset)
        self.right_panel.preset_panel.preset_load_requested.connect(self._load_preset)
        self.right_panel.preset_panel.preset_delete_requested.connect(
            self._delete_preset
        )
        self.right_panel.preset_panel.preset_selected.connect(
            self._update_preset_summary
        )
        self.controls.traj_tail_length_changed.connect(self.scene.set_traj_tail_length)
        self.controls.trajectory_panel.trajectories_changed.connect(
            self._on_trajectories_changed
        )
        self.controls.trajectory_panel.styles_changed.connect(
            self._on_trajectory_styles_changed
        )
        self.controls.custom_panel.compile_requested.connect(self._on_custom_compile)

        self.poincare_panel = PoincarePanel()
        self.poincare_panel.plane_changed.connect(self.scene.set_poincare_plane)
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
            lambda message: Window._set_temporary_app_status(self, message)
        )
        self.jupyter_console_panel.close_requested.connect(self._close_jupyter_console)
        self.lab_panel = LabPanel(self.jupyter_console_panel)
        self.lab_panel.follow_requested.connect(self._on_lab_follow_requested)

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
        self._closing_panel_dock = None
        self._closing_lab_dock = False
        self._workspace_tab_stacks = weakref.WeakSet()
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

        self.scene.build_grid(DEFAULT_GRID_HALF_SIZE)
        self._refresh_presets()
        self.controls.set_current_attractor(self.current_name)
        self._rebuild_view(self.current_name)
        self._restore_session(self._session_state)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize and obj is self.scene.container:
            self.scene.reposition_overlays()

        return super().eventFilter(obj, event)

    def _on_focus_changed(self, _old, _now):
        Window._sync_jupyter_workspace_state(self)

    def on_attractor_change(self, name):
        self.current_name = name
        self._rebuild_view(name)

    def _rebuild_view(self, name):
        if name == "Custom":
            self._rebuild_view_custom()
            return
        self._rebuild_view_from_config(ATTRACTORS[name])

    def _rebuild_view_custom(self):
        self.scene.stop_animation()
        _sync_animation_toolbar(self, False)
        self.controls.hide_standard_controls()
        if self._custom_config is not None:
            self._apply_config_to_view(self._custom_config)
        else:
            self.solver.cancel_solve()
            self.solver.cancel_lyapunov()
            self._solve_pending = False
            self._latest_projection_solutions = None
            self.scene.clear_solutions()
            _clear_lyapunov_display(self)

    def _rebuild_view_from_config(self, config):
        self.scene.stop_animation()
        _sync_animation_toolbar(self, False)
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self._restoring_view = True
        try:
            self.scene.set_info(config, self.controls.get_current_values())
            self.scene.set_camera(config)
            self.controls.configure(config)
            self.current_n = config.time_defaults.n
            self.current_t_max = config.time_defaults.t_max
            self.controls.set_traj_tail_max(self.current_n)
            _clear_lyapunov_display(self)
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

            self.scene.stop_animation()
            _sync_animation_toolbar(self, False)
            self.scene.set_camera(config)
            self.controls.configure(config)

            if config.name == "Custom":
                self.controls.custom_panel.set_from_config(config)

            self.controls.set_current_values(values)
            self.controls.set_time_values(n, t_max)
            self.current_n = n
            self.current_t_max = t_max
            self.controls.set_traj_tail_max(self.current_n)
            self.scene.set_info(config, self.controls.get_current_values())
            _clear_lyapunov_display(self)
            self.controls.trajectory_panel.reset(config)
            self.bifurcation_panel.set_config(
                config, self.controls.get_current_values()
            )
        finally:
            self._restoring_view = False
        self._update_plot()

    def _collect_session_state(self):
        values = self.controls.get_current_values()
        visual_options = Window._collect_visual_options(self)
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
            "panels": Window._collect_panel_state(self),
            "camera": self.scene.get_camera_state(),
            "selected_preset": self.controls.current_preset_name(),
        }
        dock_layout = Window._collect_workspace_dock_layout(self)
        if dock_layout is not None:
            state["workspace_dock_layout"] = dock_layout
        return state

    def _collect_panel_state(self):
        panels = {
            "projections": _panel_visible(self, "projection_panel"),
            "poincare": _panel_visible(self, "poincare_panel"),
            "bifurcation": _panel_visible(self, "bifurcation_panel"),
        }
        if hasattr(self, "lyapunov_panel"):
            panels["lyapunov"] = _panel_visible(self, "lyapunov_panel")
        if hasattr(self, "jupyter_console_panel"):
            panels["jupyter_console"] = _lab_visible(self)
        panels["performance_status"] = bool(
            getattr(
                self,
                "_process_status_visible",
                PROCESS_STATUS_DEFAULT_VISIBLE,
            )
        )
        return panels

    def _lab_plot_controller(self):
        controller = getattr(self, "lab_plot_controller", None)
        if controller is None:
            controller = LabPlotController(self)
            self.lab_plot_controller = controller
        return controller

    def _collect_visual_options(self):
        options = self.controls.get_visual_options()
        for key, attr in [
            ("point", "toolbar_point_action"),
            ("line", "toolbar_line_action"),
            ("trail", "toolbar_trail_action"),
            ("grid", "toolbar_grid_action"),
            ("orbit", "toolbar_orbit_action"),
            ("loop", "toolbar_loop_action"),
        ]:
            action = getattr(self, attr, None)
            if action is not None:
                options[key] = action.isChecked()
        if hasattr(self, "lyapunov_panel"):
            options["auto_lyapunov"] = _lyapunov_auto_enabled(self)
        return options

    def _set_visual_options(self, options):
        self.controls.set_visual_options(options)
        for key, action in [
            ("point", getattr(self, "toolbar_point_action", None)),
            ("line", getattr(self, "toolbar_line_action", None)),
            ("trail", getattr(self, "toolbar_trail_action", None)),
            ("grid", getattr(self, "toolbar_grid_action", None)),
            ("orbit", getattr(self, "toolbar_orbit_action", None)),
            ("loop", getattr(self, "toolbar_loop_action", None)),
        ]:
            if key in options and action is not None:
                action.setChecked(bool(options[key]))
        if "auto_lyapunov" in options:
            _set_lyapunov_auto_enabled(
                self,
                bool(options["auto_lyapunov"]),
            )

    def _collect_workspace_dock_layout(self):
        dock_area = getattr(self, "workspace_dock_area", None)
        if dock_area is None:
            return None

        try:
            return dock_area.saveState()
        except (AttributeError, TypeError, ValueError):
            return None

    def _restore_session(self, state):
        if not state or not _can_restore_session(state):
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
                self.scene.stop_animation()
                _sync_animation_toolbar(self, False)
                self.scene.set_camera(config)
                self.controls.configure(config)
                self.controls.custom_panel.set_from_config(config)
                self.controls.set_current_values(state.get("values", {}))
                _clear_lyapunov_display(self)
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
            Window._set_visual_options(self, visual_options)

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
                self.scene.set_trajectories(
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
                Window._set_process_status_visible(
                    self,
                    bool(panels["performance_status"]),
                )

        dock_layout = state.get("workspace_dock_layout")
        if isinstance(dock_layout, dict):
            Window._restore_workspace_dock_layout(self, dock_layout)

        restore_lab = getattr(self, "_restore_lab_live_plot_state", None)
        if restore_lab is not None:
            restore_lab(state.get("lab_live_plots"))

        self._update_plot()

        camera = state.get("camera")
        if isinstance(camera, dict):
            self.scene.set_camera_state(camera)

    def _refresh_presets(self, selected=None):
        self.controls.set_saved_presets(list_presets(self._preset_directory), selected)
        self._update_preset_summary(selected or self.controls.current_preset_name())

    def _icon(self, standard_icon):
        return self.style().standardIcon(standard_icon)

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

        self.toolbar_left_panel_action = Window._add_checked_icon_toolbar_action(
            self,
            toolbar,
            Window._side_panel_icon(self, "left"),
            True,
            lambda checked: Window._set_left_panel_visible(self, checked),
            "Show left panel",
        )
        toolbar.addSeparator()

        self.toolbar_anim_action = toolbar.addAction(
            self._icon(style_icon.SP_MediaPlay),
            "Play",
            self._on_anim_toggled,
        )
        self.toolbar_anim_action.setToolTip("Play animation")

        self.toolbar_loop_action = self._add_checked_toolbar_action(
            toolbar,
            "Loop",
            False,
            self.scene.set_loop_animation,
            "Loop animation",
            icon=Window._toolbar_icon(
                self,
                "media-playlist-repeat",
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
            ),
        )

        toolbar.addSeparator()

        reset_action = toolbar.addAction(
            self._icon(style_icon.SP_BrowserReload), "Reset"
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
            self.scene.fit_camera_to_solutions,
        )
        fit_camera_action.setToolTip("Fit view to trajectories")

        save_action = toolbar.addAction(
            self._icon(style_icon.SP_DialogSaveButton),
            "Save",
            self.scene.save_view_as_png,
        )
        save_action.setToolTip("Save view as PNG")

        toolbar.addSeparator()

        self.toolbar_point_action = self._add_checked_toolbar_action(
            toolbar,
            "Point",
            True,
            self.scene.set_point_mode,
            "Show animation head points",
            icon=Window._toolbar_icon(
                self,
                "media-record",
                QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton,
            ),
        )
        self.toolbar_line_action = self._add_checked_toolbar_action(
            toolbar,
            "Line",
            False,
            lambda checked: Window._set_line_mode(self, checked),
            "Show trajectory lines",
            icon=Window._toolbar_icon(
                self,
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
            icon=Window._toolbar_icon(
                self,
                "draw-path",
                QtWidgets.QStyle.StandardPixmap.SP_ArrowRight,
            ),
        )
        self.toolbar_grid_action = self._add_checked_toolbar_action(
            toolbar,
            "Grid",
            True,
            self.scene.set_grid_visible,
            "Show grid",
            icon=Window._toolbar_icon(
                self,
                "view-grid",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
        )
        self.toolbar_orbit_action = self._add_checked_toolbar_action(
            toolbar,
            "Orbit",
            False,
            self.scene.set_orbit_mode,
            "Orbit camera automatically",
            icon=Window._toolbar_icon(
                self,
                "object-rotate-right",
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
            ),
        )

        toolbar.addSeparator()

        solve_action = toolbar.addAction(
            Window._toolbar_icon(
                self,
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
            lambda: Window._toggle_process_status(self),
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
        self.toolbar_right_panel_action = Window._add_checked_icon_toolbar_action(
            self,
            toolbar,
            Window._side_panel_icon(self, "right"),
            True,
            lambda checked: Window._set_right_panel_visible(self, checked),
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
        Window._set_process_status_visible(
            self,
            getattr(
                self,
                "_process_status_visible",
                PROCESS_STATUS_DEFAULT_VISIBLE,
            ),
        )

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
        Window._keep_toolbar_action_from_taking_focus(self, toolbar, action)
        return action

    def _side_panel_icon(self, side):
        icon = QtGui.QIcon.fromTheme(f"sidebar-show-{side}")
        if icon.isNull():
            icon = Window._standard_icon(
                self,
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
            )
        return icon

    def _set_left_panel_visible(self, checked):
        controls = getattr(self, "controls", None)
        splitter = getattr(self, "main_splitter", None)
        if controls is None:
            return

        if checked:
            controls.show()
            if splitter is not None:
                sizes = splitter.sizes()
                if len(sizes) >= 3 and sizes[0] == 0:
                    left_size = getattr(
                        self, "_left_panel_splitter_size", int(WINDOW_WIDTH * 0.22)
                    )
                    sizes[0] = left_size
                    splitter.setSizes(sizes)
            return

        if splitter is not None:
            sizes = splitter.sizes()
            if len(sizes) >= 3 and sizes[0] > 0:
                self._left_panel_splitter_size = sizes[0]
        controls.hide()

    def _set_trail_mode(self, checked):
        self.scene.set_trail_mode(checked)
        self.controls.set_trail_options_visible(checked)

    def _set_right_panel_visible(self, checked):
        right_panel = getattr(self, "right_panel", None)
        splitter = getattr(self, "main_splitter", None)
        if right_panel is None:
            return

        if checked:
            right_panel.show()
            if splitter is not None:
                sizes = splitter.sizes()
                if len(sizes) >= 3 and sizes[2] == 0:
                    right_panel_size = getattr(
                        self, "_right_panel_splitter_size", int(WINDOW_WIDTH * 0.23)
                    )
                    sizes[2] = right_panel_size
                    splitter.setSizes(sizes)
            return

        if splitter is not None:
            sizes = splitter.sizes()
            if len(sizes) >= 3 and sizes[2] > 0:
                self._right_panel_splitter_size = sizes[2]
        right_panel.hide()

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
        if not hasattr(self, "toolbar_lyapunov_action"):
            return

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
            self.toolbar_process_status_action.setChecked(
                getattr(
                    self,
                    "_process_status_visible",
                    PROCESS_STATUS_DEFAULT_VISIBLE,
                )
            )
        Window._sync_jupyter_workspace_state(self)

    def _set_process_status_visible(self, visible):
        self._process_status_visible = bool(visible)

        status_bar_getter = getattr(self, "statusBar", None)
        status_bar = status_bar_getter() if status_bar_getter is not None else None
        process_status = getattr(self, "process_status", None)
        if process_status is not None:
            process_status.setVisible(self._process_status_visible)
            process_status.set_active(self._process_status_visible)
        if status_bar is not None:
            status_bar.setVisible(self._process_status_visible)

        action = getattr(self, "toolbar_process_status_action", None)
        if action is not None and action.isChecked() != self._process_status_visible:
            with QtCore.QSignalBlocker(action):
                action.setChecked(self._process_status_visible)

        Window._sync_status_bar_visibility(self)

    def _toggle_process_status(self):
        Window._set_process_status_visible(
            self,
            not getattr(
                self,
                "_process_status_visible",
                PROCESS_STATUS_DEFAULT_VISIBLE,
            ),
        )

    def _set_app_status(self, message, error=False):
        self._app_status_message = str(message)
        label = getattr(self, "app_status_label", None)
        if label is not None:
            colour = "#ff6b6b" if error else "#178640"
            label.setText(self._app_status_message)
            label.setStyleSheet(
                f"border: none; padding: 0 4px 3px 4px; font-size: 12px; color: {colour};"
            )
        else:
            controls = getattr(self, "controls", None)
            set_status = getattr(controls, "set_status", None)
            if set_status is not None:
                set_status(message, error=error)

        Window._sync_status_bar_visibility(self)

    def _set_temporary_app_status(self, message, *, timeout_ms=3000, error=False):
        message = str(message)
        Window._set_app_status(self, message, error=error)

        if not hasattr(self, "_app_status_clear_timer"):
            self._app_status_clear_timer = QtCore.QTimer(self)
            self._app_status_clear_timer.setSingleShot(True)

        try:
            self._app_status_clear_timer.timeout.disconnect()
        except TypeError:
            pass

        self._app_status_clear_timer.timeout.connect(
            lambda expected=message: (
                Window._clear_app_status(self)
                if getattr(self, "_app_status_message", "") == expected
                else None
            )
        )
        self._app_status_clear_timer.start(int(timeout_ms))

    def _clear_app_status(self):
        self._app_status_message = ""
        label = getattr(self, "app_status_label", None)
        if label is not None:
            label.clear()
        else:
            controls = getattr(self, "controls", None)
            clear_status = getattr(controls, "clear_status", None)
            if clear_status is not None:
                clear_status()

        Window._sync_status_bar_visibility(self)

    def _sync_status_bar_visibility(self):
        status_bar_getter = getattr(self, "statusBar", None)
        status_bar = status_bar_getter() if status_bar_getter is not None else None
        if status_bar is None:
            return

        status_bar.setVisible(
            bool(
                getattr(
                    self,
                    "_process_status_visible",
                    PROCESS_STATUS_DEFAULT_VISIBLE,
                )
                or getattr(self, "_app_status_message", "")
            )
        )

    def _build_jupyter_toolbar_actions(self, toolbar):
        self._jupyter_toolbar_actions = []
        toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        plot_item = self.jupyter_console_panel.plot_widget.getPlotItem()
        view_box = plot_item.getViewBox()

        view_all_action = toolbar.addAction(
            Window._toolbar_icon(
                self,
                "zoom-fit-best",
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton,
            ),
            "View all",
        )
        view_all_action.setToolTip("Fit all plot data")
        view_all_action.triggered.connect(view_box.autoRange)
        self._jupyter_toolbar_actions.append(view_all_action)
        Window._keep_toolbar_action_from_taking_focus(self, toolbar, view_all_action)

        mouse_group = QtGui.QActionGroup(toolbar)
        mouse_group.setExclusive(True)
        pan_action = toolbar.addAction(
            Window._toolbar_icon(
                self,
                "transform-move",
                QtWidgets.QStyle.StandardPixmap.SP_ArrowUp,
            ),
            "Pan",
        )
        pan_action.setCheckable(True)
        pan_action.setChecked(True)
        pan_action.setToolTip("Pan with left mouse button")
        zoom_action = toolbar.addAction(
            Window._toolbar_icon(
                self,
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
        Window._keep_toolbar_action_from_taking_focus(self, toolbar, pan_action)
        Window._keep_toolbar_action_from_taking_focus(self, toolbar, zoom_action)

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        for text, widget in [
            ("X grid", plot_item.ctrl.xGridCheck),
            ("Y grid", plot_item.ctrl.yGridCheck),
        ]:
            self._jupyter_toolbar_actions.append(
                Window._add_plot_option_action(self, toolbar, text, widget)
            )

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        Window._add_jupyter_plot_controls(self, toolbar)
        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        self._jupyter_toolbar_actions.append(
            Window._add_toolbar_menu_button(
                self, toolbar, "Plot", plot_item.getMenu(), "Plot options"
            )
        )
        view_menu = getattr(view_box, "menu", None)
        if view_menu is not None:
            self._jupyter_toolbar_actions.append(
                Window._add_toolbar_menu_button(
                    self, toolbar, "View", view_menu, "ViewBox options"
                )
            )

        Window._set_toolbar_actions_visible(self, self._jupyter_toolbar_actions, False)

    def _add_jupyter_plot_controls(self, toolbar):
        label = QtWidgets.QLabel("Plot")
        label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._jupyter_toolbar_actions.append(toolbar.addWidget(label))

        self.toolbar_lab_plot_combo = QtWidgets.QComboBox()
        self.toolbar_lab_plot_combo.setFixedWidth(LAB_PLOT_COMBO_WIDTH)
        self.toolbar_lab_plot_combo.currentIndexChanged.connect(
            lambda _index: Window._on_toolbar_lab_plot_selected(self)
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_lab_plot_combo)
        )

        self.toolbar_lab_plot_name = QtWidgets.QLineEdit()
        self.toolbar_lab_plot_name.setPlaceholderText("Plot name")
        self.toolbar_lab_plot_name.setMaximumWidth(130)
        self.toolbar_lab_plot_name.returnPressed.connect(
            lambda: Window._rename_current_lab_plot(self)
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.toolbar_lab_plot_name)
        )

        icon_specs = [
            (
                "New",
                "list-add",
                QtWidgets.QStyle.StandardPixmap.SP_FileIcon,
                lambda: Window._new_lab_plot(self),
                "Create a new console plot",
            ),
            (
                "Rename",
                "edit-rename",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                lambda: Window._rename_current_lab_plot(self),
                "Rename the current console plot",
            ),
            (
                "Clear",
                "edit-clear-history",
                QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton,
                lambda: Window._clear_lab_plot(self),
                "Clear the current console plot",
            ),
            (
                "Clear all",
                "edit-delete",
                QtWidgets.QStyle.StandardPixmap.SP_TrashIcon,
                lambda: Window._clear_all_lab_plots(self),
                "Clear all console plots",
            ),
        ]
        for text, theme_name, fallback_icon, callback, tooltip in icon_specs:
            action = toolbar.addAction(
                Window._toolbar_icon(self, theme_name, fallback_icon),
                text,
            )
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            self._jupyter_toolbar_actions.append(action)
            Window._keep_toolbar_action_from_taking_focus(self, toolbar, action)
        Window._sync_lab_plots(self)

    def _standard_icon(self, standard_icon):
        icon = getattr(self, "_icon", None)
        if icon is not None:
            return icon(standard_icon)
        return QtWidgets.QApplication.style().standardIcon(standard_icon)

    def _toolbar_icon(self, theme_name, fallback_icon):
        icon = QtGui.QIcon.fromTheme(theme_name)
        if icon.isNull():
            icon = Window._standard_icon(self, fallback_icon)
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
        Window._keep_toolbar_action_from_taking_focus(self, toolbar, action)
        return action

    def _add_toolbar_menu_button(self, toolbar, text, menu, tooltip=None):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        return toolbar.addWidget(button)

    def _set_toolbar_actions_visible(self, actions, visible):
        for action in actions:
            action.setVisible(visible)

    def _jupyter_toolbar_should_be_visible(self):
        return _lab_visible_to_user(self)

    def _sync_jupyter_toolbar_visibility(self):
        actions = getattr(self, "_jupyter_toolbar_actions", None)
        if actions is None:
            return
        Window._set_toolbar_actions_visible(
            self,
            actions,
            Window._jupyter_toolbar_should_be_visible(self),
        )

    def _sync_jupyter_workspace_state(self):
        Window._watch_workspace_tab_stacks(self)
        Window._sync_jupyter_toolbar_visibility(self)

    def _sync_toolbar_animation_action(self, playing):
        if not hasattr(self, "toolbar_anim_action"):
            return

        style_icon = QtWidgets.QStyle.StandardPixmap
        if playing:
            self.toolbar_anim_action.setIcon(self._icon(style_icon.SP_MediaStop))
            self.toolbar_anim_action.setText("Stop")
            self.toolbar_anim_action.setToolTip("Stop animation")
        else:
            self.toolbar_anim_action.setIcon(self._icon(style_icon.SP_MediaPlay))
            self.toolbar_anim_action.setText("Play")
            self.toolbar_anim_action.setToolTip("Play animation")

    def _open_preset_folder(self):
        Path(self._preset_directory).mkdir(parents=True, exist_ok=True)
        opened = QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(self._preset_directory)
        )
        if not opened:
            Window._set_app_status(self, "Could not open preset folder", error=True)

    def _reset_saved_session(self):
        clear_session(self._settings)
        self._session_reset_requested = True
        Window._set_app_status(self, "Saved session reset")

    def _save_session_on_close(self):
        if not self._session_reset_requested:
            save_session(self._settings, self._collect_session_state())

    def _update_preset_summary(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.controls.set_preset_notes("")
            self.controls.set_preset_summary("No saved presets")
            return

        try:
            metadata = preset_metadata(self._preset_directory, preset_name)
        except PresetError as exc:
            self.controls.set_preset_notes("")
            self.controls.set_preset_summary(str(exc))
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
        self.controls.set_preset_notes(metadata["notes"])
        self.controls.set_preset_summary(summary)

    def _default_preset_name(self):
        return f"{self.current_name} preset"

    def _save_preset(self, name, notes):
        config, values = self._get_current_config_and_values()
        if config is None:
            Window._set_app_status(self, "No attractor selected", error=True)
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
            Window._set_app_status(self, str(exc), error=True)
            return

        self._refresh_presets(preset_name)
        Window._set_app_status(self, f"Saved preset: {preset_name}")

    def _load_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            Window._set_app_status(self, "Select a preset to load", error=True)
            return

        try:
            config, values, n, t_max = load_named_preset(
                self._preset_directory, preset_name
            )
        except PresetError as exc:
            Window._set_app_status(self, str(exc), error=True)
            return

        self._apply_loaded_preset(config, values, n, t_max)
        self._refresh_presets(preset_name)
        Window._set_app_status(self, f"Loaded preset: {preset_name}")

    def _delete_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            Window._set_app_status(self, "Select a preset to delete", error=True)
            return

        try:
            delete_named_preset(self._preset_directory, preset_name)
        except PresetError as exc:
            Window._set_app_status(self, str(exc), error=True)
            return

        self._refresh_presets()
        Window._set_app_status(self, f"Deleted preset: {preset_name}")

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

    def _update_plot(self):
        self.scene.stop_animation()
        _sync_animation_toolbar(self, False)
        self.solver.cancel_solve()
        self.solver.cancel_lyapunov()
        self._solve_pending = False
        self._dispatch_solve(full=True)
        config, values = self._get_current_config_and_values()
        if config is not None:
            self.scene.set_info(config, values)

    def _dispatch_solve(self, full=False):
        if self._solve_pending:
            return
        self._solve_pending = True
        self._solve_needed = False
        config, values = self._get_current_config_and_values()
        if config is None:
            self._solve_pending = False
            return
        user_n = self.current_n or config.time_defaults.n
        t_max = self.current_t_max
        ics = self.controls.trajectory_panel.get_trajectories()
        ic_list = [t["ic"] for t in ics] if ics else [config.initial_conditions]
        dispatch_n = user_n if full else min(user_n, PARTIAL_N)
        self.solver.cancel_lyapunov()
        if full:
            self.controls.set_status(_solve_status_text(len(ic_list)))
        self._active_solve_request_id = self.solver.request_solve(
            config, values, ic_list, dispatch_n, not full, t_max
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
        self.scene.stop_animation()
        _sync_animation_toolbar(self, False)
        if (
            not full
            and self._solve_pending
            and getattr(self, "_solve_state", {}).get("partial", False)
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
        return _lyapunov_auto_enabled(self)

    def _request_lyapunov(self, config=None, values=None):
        if _has_hidden_lyapunov_panel(self):
            return

        if config is None or values is None:
            config, values = self._get_current_config_and_values()
        if config is None:
            Window._set_app_status(self, "No attractor selected", error=True)
            return

        self.solver.cancel_lyapunov()
        Window._set_app_status(self, "Computing Lyapunov spectrum")
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

        solve_token = getattr(self, "_solve_perf_tokens", {}).pop(request_id, None)
        self._solve_pending = False

        if solutions is None:
            perf_finish(self, solve_token, status="failed", partial=is_partial)
            _set_solve_state(
                self,
                solving=False,
                valid=False,
                stale=_has_console_solutions(self),
                partial=False,
                last_error="Solve failed",
                solution_points=[],
            )
            if self._solve_needed:
                self._solve_needed = False
                self._dispatch_solve(full=self._full_needed)
            else:
                Window._set_app_status(self, "Solve failed", error=True)
            return

        is_valid, message = validate_solutions(solutions)
        if not is_valid:
            perf_finish(self, solve_token, status="invalid", partial=is_partial)
            _set_solve_state(
                self,
                solving=False,
                valid=False,
                stale=_has_console_solutions(self),
                partial=False,
                last_error=message,
                solution_points=[],
            )
            Window._set_app_status(self, message, error=True)
            if self._solve_needed:
                self._solve_needed = False
                full = self._full_needed
                self._full_needed = False
                self._dispatch_solve(full=full)
            return

        perf_finish(self, solve_token, status="ok", partial=is_partial)
        Window._clear_app_status(self)
        self.scene.display_solutions(solutions, is_partial)

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
            self.scene.auto_adjust_grid(solutions)
            refresh_lab = getattr(self, "_refresh_lab_live_plots", None)
            if refresh_lab is not None:
                refresh_lab()

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

    def _reapply_projections(self):
        solutions = self._latest_projection_solutions or self.scene.get_solutions()
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

    def _reset_camera(self):
        config, _ = self._get_current_config_and_values()
        if config is not None:
            self.scene.set_camera(config)

    def _on_anim_toggled(self):
        playing = self.scene.toggle_animation()
        _sync_animation_toolbar(self, playing)

    def _on_anim_finished(self):
        _sync_animation_toolbar(self, False)

    def _on_n_changed(self, val):
        self.current_n = val
        self.controls.set_traj_tail_max(val)

    def _on_t_max_changed(self, val):
        self.current_t_max = val

    def _on_trajectories_changed(self, trajectories):
        self.scene.set_trajectories(trajectories)
        if getattr(self, "_restoring_view", False):
            return

        self._latest_projection_solutions = None
        self.scene.clear_solutions()
        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _on_trajectory_styles_changed(self, trajectories):
        self.scene.set_trajectories(trajectories)
        self.scene.refresh_colours()

    def _on_lyapunov_result(self, request_id, lyap, ky_dim, t_hist, lyap_hist):
        if request_id != self._active_lyapunov_request_id:
            return
        if _has_hidden_lyapunov_panel(self):
            return

        token = getattr(self, "_lyapunov_perf_tokens", {}).pop(request_id, None)
        perf_finish(self, token)
        _set_lyapunov_display(self, lyap, ky_dim, t_hist, lyap_hist)
        Window._clear_app_status(self)

    def _on_lyapunov_failed(self, request_id, message):
        if request_id != self._active_lyapunov_request_id:
            return
        if _has_hidden_lyapunov_panel(self):
            self._cancel_lyapunov_analysis()
            return

        token = getattr(self, "_lyapunov_perf_tokens", {}).pop(request_id, None)
        perf_finish(self, token, status="failed")
        Window._set_app_status(self, f"Lyapunov failed: {message}", error=True)

    def _panel_dock_for(self, panel):
        for dock in getattr(self, "_panel_docks", {}).values():
            if panel in dock.widgets:
                return dock
        return None

    def _connect_workspace_dock_signals(self):
        docks = [getattr(self, "viewport_dock", None)]
        docks.append(getattr(self, "lab_dock", None))
        docks.extend(getattr(self, "_panel_docks", {}).values())
        for dock in docks:
            if dock is None:
                continue
            signal = getattr(dock, "container_changed", None)
            if signal is not None:
                signal.connect(self._on_workspace_layout_changed)

    def _on_workspace_layout_changed(self):
        QtCore.QTimer.singleShot(0, self._sync_jupyter_workspace_state)

    def _watch_workspace_tab_stacks(self):
        dock_area = getattr(self, "workspace_dock_area", None)
        if dock_area is None:
            return

        watched = getattr(self, "_workspace_tab_stacks", None)
        if watched is None:
            watched = weakref.WeakSet()
            self._workspace_tab_stacks = watched

        try:
            containers, _docks = dock_area.findAll()
        except (AttributeError, RuntimeError):
            return

        for container in containers:
            stack = getattr(container, "stack", None)
            if stack is None or stack in watched:
                continue
            stack.currentChanged.connect(
                lambda _index: Window._sync_jupyter_workspace_state(self)
            )
            watched.add(stack)

    def _restore_workspace_dock_layout(self, dock_layout):
        dock_area = getattr(self, "workspace_dock_area", None)
        if dock_area is None:
            return

        try:
            dock_area.restoreState(dock_layout, missing="ignore", extra="bottom")
        except Exception:  # noqa: BLE001
            return
        Window._sync_jupyter_workspace_state(self)

    def _replace_closed_lab_dock(self):
        dock = Window._build_lab_dock(self)
        signal = getattr(dock, "container_changed", None)
        on_layout_changed = getattr(self, "_on_workspace_layout_changed", None)
        if signal is not None and on_layout_changed is not None:
            signal.connect(on_layout_changed)
        self.lab_dock = dock

    def _open_lab_dock(self):
        dock = getattr(self, "lab_dock", None)
        if dock is None:
            self.lab_panel.show()
            return

        if dock.container() is None:
            self.workspace_dock_area.addDock(
                dock,
                position="above",
                relativeTo=self.viewport_dock,
            )
        self.lab_panel.show()
        container = dock.container()
        if hasattr(container, "raiseDock"):
            dock.raiseDock()
        Window._sync_jupyter_workspace_state(self)

    def _panel_name_for_panel(self, panel):
        for panel_name, dock in getattr(self, "_panel_docks", {}).items():
            if panel in dock.widgets:
                return panel_name
        return None

    def _replace_closed_panel_dock(self, panel_name, panel):
        titles = getattr(self, "_panel_dock_titles", {})
        title = titles.get(panel_name)
        if title is None:
            return

        dock = Window._build_panel_dock(self, title, panel)
        signal = getattr(dock, "container_changed", None)
        on_layout_changed = getattr(self, "_on_workspace_layout_changed", None)
        if signal is not None and on_layout_changed is not None:
            signal.connect(on_layout_changed)
        self._panel_docks[panel_name] = dock

    def _open_panel_dock(self, panel, panel_name):
        dock = getattr(self, "_panel_docks", {}).get(panel_name)
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
        container = dock.container()
        if hasattr(container, "raiseDock"):
            dock.raiseDock()
        Window._sync_jupyter_workspace_state(self)

    def _close_panel_dock(self, panel):
        dock = Window._panel_dock_for(self, panel)
        if dock is None:
            close_split_panel = getattr(self, "_close_split_panel", None)
            if close_split_panel is not None:
                return close_split_panel(panel)
            return 0

        if dock.container() is not None and self._closing_panel_dock is not dock:
            self._closing_panel_dock = dock
            try:
                dock.close()
            finally:
                self._closing_panel_dock = None
        return 0

    def _on_panel_dock_closed(self, panel):
        panel_name = Window._panel_name_for_panel(self, panel)
        dock = Window._panel_dock_for(self, panel)
        if getattr(self, "_closing_panel_dock", None) is dock:
            if panel_name is not None:
                Window._replace_closed_panel_dock(self, panel_name, panel)
            return

        if panel is getattr(self, "lyapunov_panel", None):
            self._close_lyapunov_panel()
        elif panel is getattr(self, "projection_panel", None):
            self._close_projections()
        elif panel is getattr(self, "poincare_panel", None):
            self._close_poincare()
        elif panel is getattr(self, "bifurcation_panel", None):
            self._close_bifurcation()

        if panel_name is not None:
            Window._replace_closed_panel_dock(self, panel_name, panel)

    def _cancel_lyapunov_analysis(self):
        cancel = getattr(self.solver, "cancel_lyapunov", None)
        if cancel is not None:
            cancel()

        request_id = getattr(self, "_active_lyapunov_request_id", None)
        if request_id is not None:
            token = getattr(self, "_lyapunov_perf_tokens", {}).pop(request_id, None)
            perf_finish(self, token, status="cancelled")
        self._active_lyapunov_request_id = None
        Window._clear_app_status(self)

    def _close_lyapunov_panel(self):
        Window._cancel_lyapunov_analysis(self)
        self.lyapunov_panel.hide()
        size = Window._close_panel_dock(self, self.lyapunov_panel)
        if size > 0:
            self._lyapunov_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_lyapunov_panel(self):
        if _panel_visible(self, "lyapunov_panel"):
            self._close_lyapunov_panel()
        else:
            Window._open_panel_dock(self, self.lyapunov_panel, "lyapunov_panel")
            if self.lyapunov_panel.auto_enabled():
                self._request_lyapunov()
            _sync_panel_toolbar(self)

    def _close_projections(self):
        self.projection_panel.hide()
        size = Window._close_panel_dock(self, self.projection_panel)
        if size > 0:
            self._projection_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_projections(self):
        if _panel_visible(self, "projection_panel"):
            self._close_projections()
        else:
            Window._open_panel_dock(self, self.projection_panel, "projection_panel")
            QtCore.QTimer.singleShot(0, self._reapply_projections)
            QtCore.QTimer.singleShot(50, self._reapply_projections)
            _sync_panel_toolbar(self)

    def _close_poincare(self):
        self.poincare_panel.cancel_solve()
        self.scene.remove_poincare_plane()
        self.poincare_panel.hide()
        size = Window._close_panel_dock(self, self.poincare_panel)
        if size > 0:
            self._poincare_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_poincare(self):
        if _panel_visible(self, "poincare_panel"):
            self._close_poincare()
        else:
            Window._open_panel_dock(self, self.poincare_panel, "poincare_panel")
            self.scene.set_poincare_plane(
                self.poincare_panel.plane_combo.currentText(),
                self.poincare_panel.value_spin.value(),
            )
            self.poincare_panel.recompute()
            config, values = self._get_current_config_and_values()
            if config is not None:
                self.poincare_panel.set_attractor(config, values)
            _sync_panel_toolbar(self)

    def _close_bifurcation(self):
        self.bifurcation_panel.cancel_sweep()
        self.bifurcation_panel.hide()
        size = Window._close_panel_dock(self, self.bifurcation_panel)
        if size > 0:
            self._bifurcation_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_bifurcation(self):
        if _panel_visible(self, "bifurcation_panel"):
            self._close_bifurcation()
        else:
            config, values = self._get_current_config_and_values()
            if config is None:
                return
            self.bifurcation_panel.set_config(config, values)
            Window._open_panel_dock(
                self,
                self.bifurcation_panel,
                "bifurcation_panel",
            )
            _sync_panel_toolbar(self)

    def _new_lab_plot(self):
        self.jupyter_console_panel.plots.new()
        Window._sync_jupyter_workspace_state(self)

    def _rename_current_lab_plot(self):
        old_name = self.jupyter_console_panel.plots.current_name
        new_name = self.toolbar_lab_plot_name.text().strip()
        if new_name:
            Window._rename_lab_plot(self, old_name, new_name)

    def _rename_lab_plot(self, old_name, new_name):
        return Window._lab_plot_controller(self)._rename_lab_plot(old_name, new_name)

    def _sync_lab_plots(self):
        return Window._lab_plot_controller(self)._sync_lab_plots()

    def _lab_plot_combo_label(self, plot_name):
        return Window._lab_plot_controller(self)._lab_plot_combo_label(plot_name)

    def _lab_plot_combo_tooltip(self, plot_name):
        return Window._lab_plot_controller(self)._lab_plot_combo_tooltip(plot_name)


    def _run_console_plot_request(self, kind, *, plot=None, **options):
        return Window._lab_plot_controller(self)._run_console_plot_request(
            kind, plot=plot, **options
        )

    def _on_lab_plots_changed(self):
        return Window._lab_plot_controller(self)._on_lab_plots_changed()

    def _clear_lab_plot(self):
        return Window._lab_plot_controller(self)._clear_lab_plot()

    def _clear_all_lab_plots(self):
        return Window._lab_plot_controller(self)._clear_all_lab_plots()

    def _close_lab_plot(self):
        return Window._lab_plot_controller(self)._close_lab_plot()


    def _on_lab_dock_closed(self):
        if not getattr(self, "_closing_lab_dock", False):
            self.lab_panel.hide()
        Window._replace_closed_lab_dock(self)
        Window._sync_jupyter_workspace_state(self)
        _sync_panel_toolbar(self)

    def _close_jupyter_console(self):
        dock = getattr(self, "lab_dock", None)
        if dock is not None and dock.container() is not None:
            self._closing_lab_dock = True
            try:
                dock.close()
            finally:
                self._closing_lab_dock = False
        self.lab_panel.hide()
        Window._sync_jupyter_workspace_state(self)
        _sync_panel_toolbar(self)

    def _toggle_jupyter_console(self):
        if _lab_visible(self):
            self._close_jupyter_console()
        else:
            self.jupyter_console_panel.ensure_console()
            Window._open_lab_dock(self)
            self.jupyter_console_panel.focus_console()
            Window._sync_jupyter_workspace_state(self)
            _sync_panel_toolbar(self)

    def closeEvent(self, a0):
        self._save_session_on_close()
        self.jupyter_console_panel.shutdown_kernel()
        self.scene.set_orbit_mode(False)
        self.scene.stop_animation()
        self.solver.shutdown()
        super().closeEvent(a0)
