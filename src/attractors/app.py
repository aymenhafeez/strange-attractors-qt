from pathlib import Path

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .bifurcation_panel import BifurcationPanel
from .control_panel import ControlPanel
from .grid_overlay import DEFAULT_GRID_HALF_SIZE
from .jupyter_console_panel import JupyterConsolePanel
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
from .projection_panel import ProjectionPanel
from .registry import ATTRACTORS
from .session import clear_session, load_session, save_session, session_settings
from .solution_validation import validate_solutions
from .solve_manager import SolveManager
from .style import SPLITTER_HANDLE
from .view_manager import ViewManager

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PARTIAL_N = 40000
PROJECTION_UPDATE_INTERVAL_MS = 100
MAIN_VIEW_MARGIN = 8
TOOLBAR_ICON_SIZE = 18


def _should_update_projection(now_ms, last_update_ms, interval_ms):
    if last_update_ms is None:
        return True

    return now_ms - last_update_ms >= interval_ms


def _solve_status_text(n_trajectories):
    if n_trajectories == 1:
        return "Solving trajectory"
    return f"Solving {n_trajectories} trajectories"


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
    panel = getattr(window, panel_name, None)
    return bool(panel is not None and panel.isVisible())


def _has_hidden_lyapunov_panel(window):
    panel = getattr(window, "lyapunov_panel", None)
    return bool(panel is not None and not panel.isVisible())


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
        self._latest_projection_solutions = None
        self._settings = session_settings()
        self._session_state = load_session(self._settings)
        self._session_reset_requested = False
        self._perf = PerfProfiler()
        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = _session_attractor_name(self._session_state)
        self._custom_config = None
        self._preset_directory = _preset_directory()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.solver = SolveManager(self)
        self.solver.solutions_ready.connect(self._on_solve_result)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)
        self.solver.lyapunov_failed.connect(self._on_lyapunov_failed)

        self.scene = ViewManager(self)
        self.scene.animation_finished.connect(self._on_anim_finished)
        self.scene.projections_data.connect(self._on_projections_data)

        self.controls = ControlPanel()
        self.controls.attractor_changed.connect(self.on_attractor_change)
        self.controls.solve_requested.connect(self._on_controls_solve_requested)
        self.controls.lyapunov_requested.connect(self._on_lyapunov_requested)
        self.controls.projections_requested.connect(self._toggle_projections)
        self.controls.bifurcation_requested.connect(self._toggle_bifurcation)
        self.controls.poincare_requested.connect(self._toggle_poincare)
        self.controls.jupyter_console_requested.connect(self._toggle_jupyter_console)
        self.controls.n_changed.connect(self._on_n_changed)
        self.controls.t_max_changed.connect(self._on_t_max_changed)
        self.controls.animation_toggled.connect(self._on_anim_toggled)
        self.controls.animation_speed_changed.connect(self.scene.set_anim_step)
        self.controls.orbit_toggled.connect(self.scene.set_orbit_mode)
        self.controls.orbit_speed_changed.connect(self.scene.set_orbit_speed)
        self.controls.point_button.toggled.connect(self.scene.set_point_mode)
        self.controls.line_mode.toggled.connect(self.scene.set_line_mode)
        self.controls.trail_mode.toggled.connect(self.scene.set_trail_mode)
        self.controls.show_grid.toggled.connect(self.scene.set_grid_visible)
        self.controls.alpha_slider.valueChanged.connect(self.scene.set_alpha)
        self.controls.alpha_spin.valueChanged.connect(self.scene.set_alpha)
        self.controls.save_requested.connect(self.scene.save_view_as_png)
        self.controls.preset_folder_requested.connect(self._open_preset_folder)
        self.controls.session_reset_requested.connect(self._reset_saved_session)
        self.controls.preset_save_requested.connect(self._save_preset)
        self.controls.preset_load_requested.connect(self._load_preset)
        self.controls.preset_delete_requested.connect(self._delete_preset)
        self.controls.preset_selected.connect(self._update_preset_summary)
        self.controls.camera_reset_requested.connect(self._reset_camera)
        self.controls.camera_fit_requested.connect(self.scene.fit_camera_to_solutions)
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

        self._poincare_splitter_size = 400

        self.lyapunov_panel = LyapunovPanel()
        self.lyapunov_panel.compute_requested.connect(self._on_lyapunov_requested)
        self.lyapunov_panel.close_requested.connect(self._close_lyapunov_panel)
        self.lyapunov_panel.hide()

        self._lyapunov_splitter_size = 260

        self.projection_panel = ProjectionPanel()
        self.projection_panel.close_requested.connect(self._close_projections)
        self.projection_panel.hide()

        self._projection_splitter_size = 260

        self.bifurcation_panel = BifurcationPanel()
        self.bifurcation_panel.close_requested.connect(self._close_bifurcation)
        self.bifurcation_panel.hide()

        self._bifurcation_splitter_size = 500

        self.jupyter_console_panel = JupyterConsolePanel(
            self._jupyter_console_namespace
        )
        self.jupyter_console_panel.close_requested.connect(self._close_jupyter_console)
        self.jupyter_console_panel.hide()

        self._normal_splitter_sizes = None

        self._build_toolbar()

        self.inner_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.inner_splitter.addWidget(self.lyapunov_panel)
        self.inner_splitter.addWidget(self.poincare_panel)
        self.inner_splitter.addWidget(self.bifurcation_panel)
        self.inner_splitter.addWidget(self.scene.container)
        self.inner_splitter.addWidget(self.projection_panel)
        self.inner_splitter.setSizes([0, 0, 0, 600, 0])
        self.inner_splitter.setStyleSheet(SPLITTER_HANDLE)

        main_area = QtWidgets.QWidget()
        main_area_layout = QtWidgets.QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(
            0,
            MAIN_VIEW_MARGIN,
            MAIN_VIEW_MARGIN,
            MAIN_VIEW_MARGIN,
        )
        self.main_stack = QtWidgets.QStackedWidget()
        self.main_stack.addWidget(self.inner_splitter)
        self.main_stack.addWidget(self.jupyter_console_panel)
        main_area_layout.addWidget(self.main_stack)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.controls)
        self.main_splitter.addWidget(main_area)
        self.main_splitter.setSizes([int(WINDOW_WIDTH * 0.3), int(WINDOW_WIDTH * 0.7)])
        self.main_splitter.setStyleSheet(SPLITTER_HANDLE)
        layout.addWidget(self.main_splitter)

        self.scene.container.installEventFilter(self)

        self.scene.build_grid(DEFAULT_GRID_HALF_SIZE)
        self._refresh_presets()
        self.controls.set_current_attractor(self.current_name)
        self._rebuild_view(self.current_name)
        self._restore_session(self._session_state)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize and obj is self.scene.container:
            self.scene.reposition_overlays()

        return super().eventFilter(obj, event)

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
        self.controls.set_anim_playing(False)
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
        self.controls.set_anim_playing(False)
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
            self.controls.set_anim_playing(False)
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
        visual_options = self.controls.get_visual_options()
        if hasattr(self, "lyapunov_panel"):
            visual_options["auto_lyapunov"] = _lyapunov_auto_enabled(self)
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

        return {
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

    def _collect_panel_state(self):
        panels = {
            "projections": _panel_visible(self, "projection_panel"),
            "poincare": _panel_visible(self, "poincare_panel"),
            "bifurcation": _panel_visible(self, "bifurcation_panel"),
        }
        if hasattr(self, "lyapunov_panel"):
            panels["lyapunov"] = _panel_visible(self, "lyapunov_panel")
        if hasattr(self, "jupyter_console_panel"):
            panels["jupyter_console"] = _panel_visible(self, "jupyter_console_panel")
        return panels

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
                self.controls.set_anim_playing(False)
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
            self.controls.set_visual_options(visual_options)
            if "auto_lyapunov" in visual_options:
                _set_lyapunov_auto_enabled(
                    self,
                    bool(visual_options["auto_lyapunov"]),
                )

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
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.scene_toolbar = toolbar

        style_icon = QtWidgets.QStyle.StandardPixmap

        self.toolbar_anim_action = toolbar.addAction(
            self._icon(style_icon.SP_MediaPlay),
            "Play",
            self._on_anim_toggled,
        )
        self.toolbar_anim_action.setToolTip("Play animation")

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
        fit_camera_action.triggered.connect(self.scene.fit_camera_to_solutions)

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
            self.controls.point_button,
            "Show animation head points",
        )
        self.toolbar_line_action = self._add_checked_toolbar_action(
            toolbar,
            "Line",
            self.controls.line_mode,
            "Show trajectory lines",
        )
        self.toolbar_trail_action = self._add_checked_toolbar_action(
            toolbar,
            "Trail",
            self.controls.trail_mode,
            "Show animated trajectory trails",
        )
        self.toolbar_grid_action = self._add_checked_toolbar_action(
            toolbar,
            "Grid",
            self.controls.show_grid,
            "Show reference grid",
        )
        self.toolbar_orbit_action = self._add_checked_toolbar_action(
            toolbar,
            "Orbit",
            self.controls.orbit_mode,
            "Orbit camera automatically",
        )

        toolbar.addSeparator()

        solve_action = toolbar.addAction("Solve")
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
        tools_menu.addSeparator()
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
            "Jupyter console",
            self._toggle_jupyter_console,
        )
        tools_menu.addSeparator()
        open_folder_action = tools_menu.addAction("Open preset folder")
        open_folder_action.triggered.connect(self._open_preset_folder)
        reset_session_action = tools_menu.addAction("Reset saved session")
        reset_session_action.triggered.connect(self._reset_saved_session)
        self.tools_button.setMenu(tools_menu)
        toolbar.addWidget(self.tools_button)
        self._main_toolbar_actions = list(toolbar.actions())
        self._build_jupyter_toolbar_actions(toolbar)
        self._sync_toolbar_panel_actions()

    def _add_checked_toolbar_action(self, toolbar, text, checkbox, tooltip):
        action = toolbar.addAction(text)
        action.setCheckable(True)
        action.setChecked(checkbox.isChecked())
        action.setToolTip(tooltip)
        action.toggled.connect(checkbox.setChecked)
        checkbox.toggled.connect(action.setChecked)
        return action

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
            self.toolbar_jupyter_console_action.setChecked(
                _panel_visible(self, "jupyter_console_panel")
            )

    def _build_jupyter_toolbar_actions(self, toolbar):
        self._jupyter_toolbar_actions = []
        self._jupyter_toolbar_actions.append(toolbar.addSeparator())

        plot_item = self.jupyter_console_panel.plot_widget.getPlotItem()
        view_box = plot_item.getViewBox()

        view_all_action = toolbar.addAction("View all")
        view_all_action.setToolTip("Fit all plot data")
        view_all_action.triggered.connect(view_box.autoRange)
        self._jupyter_toolbar_actions.append(view_all_action)

        mouse_group = QtGui.QActionGroup(toolbar)
        mouse_group.setExclusive(True)
        pan_action = toolbar.addAction("Pan")
        pan_action.setCheckable(True)
        pan_action.setChecked(True)
        pan_action.setToolTip("Pan with left mouse button")
        zoom_action = toolbar.addAction("Zoom")
        zoom_action.setCheckable(True)
        zoom_action.setToolTip("Zoom to rectangle with left mouse button")
        mouse_group.addAction(pan_action)
        mouse_group.addAction(zoom_action)
        pan_action.triggered.connect(lambda: view_box.setLeftButtonAction("pan"))
        zoom_action.triggered.connect(lambda: view_box.setLeftButtonAction("rect"))
        self._jupyter_toolbar_actions.extend([pan_action, zoom_action])

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        for text, widget in [
            ("X grid", plot_item.ctrl.xGridCheck),
            ("Y grid", plot_item.ctrl.yGridCheck),
            ("Log X", plot_item.ctrl.logXCheck),
            ("Log Y", plot_item.ctrl.logYCheck),
            ("FFT", plot_item.ctrl.fftCheck),
        ]:
            self._jupyter_toolbar_actions.append(
                Window._add_plot_option_action(self, toolbar, text, widget)
            )

        self._jupyter_toolbar_actions.append(toolbar.addSeparator())
        self._jupyter_toolbar_actions.append(
            Window._add_toolbar_menu_button(
                self, toolbar, "Plot options", plot_item.getMenu()
            )
        )
        view_menu = getattr(view_box, "menu", None)
        if view_menu is not None:
            self._jupyter_toolbar_actions.append(
                Window._add_toolbar_menu_button(
                    self, toolbar, "ViewBox options", view_menu
                )
            )

        Window._set_toolbar_actions_visible(self, self._jupyter_toolbar_actions, False)

    def _add_plot_option_action(self, toolbar, text, widget):
        action = toolbar.addAction(text)
        action.setCheckable(True)
        action.setChecked(widget.isChecked())
        action.toggled.connect(widget.setChecked)
        widget.toggled.connect(action.setChecked)
        return action

    def _add_toolbar_menu_button(self, toolbar, text, menu):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        return toolbar.addWidget(button)

    def _set_toolbar_actions_visible(self, actions, visible):
        for action in actions:
            action.setVisible(visible)

    def _set_jupyter_console_mode(self, enabled):
        if enabled:
            if self._normal_splitter_sizes is None:
                self._normal_splitter_sizes = self.main_splitter.sizes()
            self.scene.stop_animation()
            self.scene.set_orbit_mode(False)
            self.controls.set_anim_playing(False)
            _sync_animation_toolbar(self, False)
            self.controls.hide()
            Window._set_toolbar_actions_visible(self, self._main_toolbar_actions, False)
            Window._set_toolbar_actions_visible(
                self, self._jupyter_toolbar_actions, True
            )
            self.main_stack.setCurrentWidget(self.jupyter_console_panel)
            return

        self.main_stack.setCurrentWidget(self.inner_splitter)
        Window._set_toolbar_actions_visible(self, self._jupyter_toolbar_actions, False)
        Window._set_toolbar_actions_visible(self, self._main_toolbar_actions, True)
        self.controls.show()
        if self._normal_splitter_sizes is not None:
            self.main_splitter.setSizes(self._normal_splitter_sizes)
            self._normal_splitter_sizes = None

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
            self.controls.set_status("Could not open preset folder", error=True)

    def _reset_saved_session(self):
        clear_session(self._settings)
        self._session_reset_requested = True
        self.controls.set_status("Saved session reset")

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
            self.controls.set_status("No attractor selected", error=True)
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
            self.controls.set_status(str(exc), error=True)
            return

        self._refresh_presets(preset_name)
        self.controls.set_status(f"Saved preset: {preset_name}")

    def _load_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.controls.set_status("Select a preset to load", error=True)
            return

        try:
            config, values, n, t_max = load_named_preset(
                self._preset_directory, preset_name
            )
        except PresetError as exc:
            self.controls.set_status(str(exc), error=True)
            return

        self._apply_loaded_preset(config, values, n, t_max)
        self._refresh_presets(preset_name)
        self.controls.set_status(f"Loaded preset: {preset_name}")

    def _delete_preset(self, name):
        preset_name = name.strip()
        if not preset_name:
            self.controls.set_status("Select a preset to delete", error=True)
            return

        try:
            delete_named_preset(self._preset_directory, preset_name)
        except PresetError as exc:
            self.controls.set_status(str(exc), error=True)
            return

        self._refresh_presets()
        self.controls.set_status(f"Deleted preset: {preset_name}")

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
        return {
            "np": np,
            "window": self,
            "scene": self.scene,
            "view": self.scene.view,
            "controls": self.controls,
            "plot_widget": self.jupyter_console_panel.plot_widget,
            "pw": self.jupyter_console_panel.plot_widget,
            "get_solutions": self.scene.get_solutions,
            "current_config": lambda: self._get_current_config_and_values()[0],
            "current_values": lambda: self._get_current_config_and_values()[1],
            "pg": pg,
        }

    def _update_plot(self):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
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
            t_max=t_max,
            trajectories=len(ic_list),
        )
        if token is not None:
            self._solve_perf_tokens[self._active_solve_request_id] = token

    def _on_controls_solve_requested(self, full):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
        _sync_animation_toolbar(self, False)
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
            self.controls.set_status("No attractor selected", error=True)
            return

        self.solver.cancel_lyapunov()
        self.controls.set_status("Computing Lyapunov spectrum")
        self._active_lyapunov_request_id = self.solver.request_lyapunov(config, values)
        token = perf_start(
            self,
            "lyapunov",
            key=self._active_lyapunov_request_id,
            attractor=config.name,
        )
        if token is not None:
            self._lyapunov_perf_tokens[self._active_lyapunov_request_id] = token

    def _on_lyapunov_requested(self):
        self._request_lyapunov()

    def _on_solve_result(self, request_id, solutions, is_partial):
        if request_id != self._active_solve_request_id:
            if is_partial and solutions is not None:
                is_valid, _ = validate_solutions(solutions)
                if is_valid:
                    self.scene.display_solutions(solutions, is_partial)
            return

        solve_token = getattr(self, "_solve_perf_tokens", {}).pop(request_id, None)
        self._solve_pending = False

        if solutions is None:
            perf_finish(self, solve_token, status="failed", partial=is_partial)
            if self._solve_needed:
                self._solve_needed = False
                self._dispatch_solve(full=self._full_needed)
            else:
                self.controls.set_status("Solve failed", error=True)
            return

        is_valid, message = validate_solutions(solutions)
        if not is_valid:
            perf_finish(self, solve_token, status="invalid", partial=is_partial)
            self.controls.set_status(message, error=True)
            if self._solve_needed:
                self._solve_needed = False
                full = self._full_needed
                self._full_needed = False
                self._dispatch_solve(full=full)
            return

        perf_finish(self, solve_token, status="ok", partial=is_partial)
        self.controls.clear_status()
        self.scene.display_solutions(solutions, is_partial)

        if not is_partial:
            self._latest_projection_solutions = solutions
            config, values = self._get_current_config_and_values()
            if config is not None:
                if self.poincare_panel.isVisible():
                    self.poincare_panel.set_attractor(config, values)
                if self._auto_lyapunov_enabled():
                    self._request_lyapunov(config, values)
            self._update_projection_panel_from_solutions(solutions)
            if self.projection_panel.isVisible() and self._initial_full_solves == 0:
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1
            self.scene.auto_adjust_grid(solutions)

        if self._solve_needed:
            self._solve_needed = False
            full = self._full_needed
            self._full_needed = False
            self._dispatch_solve(full=full)

    def _reapply_projections(self):
        solutions = self._latest_projection_solutions or self.scene.get_solutions()
        self.projection_panel.reapply_projections(solutions)

    def _update_projection_panel_from_solutions(self, solutions):
        if not self.projection_panel.isVisible():
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
        if not self.projection_panel.isVisible():
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
        self.controls.set_anim_playing(playing)
        _sync_animation_toolbar(self, playing)

    def _on_anim_finished(self):
        self.controls.set_anim_playing(False)
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
        self.controls.clear_status()

    def _on_lyapunov_failed(self, request_id, message):
        if request_id != self._active_lyapunov_request_id:
            return
        if _has_hidden_lyapunov_panel(self):
            self._cancel_lyapunov_analysis()
            return

        token = getattr(self, "_lyapunov_perf_tokens", {}).pop(request_id, None)
        perf_finish(self, token, status="failed")
        self.controls.set_status(f"Lyapunov failed: {message}", error=True)

    def _main_view_splitter_index(self):
        return self.inner_splitter.indexOf(self.scene.container)

    def _set_split_panel_size(self, panel, height):
        sizes = self.inner_splitter.sizes()
        panel_idx = self.inner_splitter.indexOf(panel)
        main_idx = self._main_view_splitter_index()
        if panel_idx < 0 or main_idx < 0:
            return

        total = sum(sizes)
        sizes[main_idx] = max(total - height, 100)
        sizes[panel_idx] = height
        self.inner_splitter.setSizes(sizes)

    def _close_split_panel(self, panel):
        sizes = self.inner_splitter.sizes()
        idx = self.inner_splitter.indexOf(panel)
        if idx >= 0:
            size = sizes[idx]
            sizes[idx] = 0
            self.inner_splitter.setSizes(sizes)
            return size

        return 0

    def _cancel_lyapunov_analysis(self):
        cancel = getattr(self.solver, "cancel_lyapunov", None)
        if cancel is not None:
            cancel()

        request_id = getattr(self, "_active_lyapunov_request_id", None)
        if request_id is not None:
            token = getattr(self, "_lyapunov_perf_tokens", {}).pop(request_id, None)
            perf_finish(self, token, status="cancelled")
        self._active_lyapunov_request_id = None
        self.controls.clear_status()

    def _close_lyapunov_panel(self):
        Window._cancel_lyapunov_analysis(self)
        self.lyapunov_panel.hide()
        size = self._close_split_panel(self.lyapunov_panel)
        if size > 0:
            self._lyapunov_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_lyapunov_panel(self):
        if self.lyapunov_panel.isVisible():
            self._close_lyapunov_panel()
        else:
            self.lyapunov_panel.show()
            h = max(self._lyapunov_splitter_size, 150)
            self._set_split_panel_size(self.lyapunov_panel, h)
            if self.lyapunov_panel.auto_enabled():
                self._request_lyapunov()
            _sync_panel_toolbar(self)

    def _close_projections(self):
        self.projection_panel.hide()
        size = self._close_split_panel(self.projection_panel)
        if size > 0:
            self._projection_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_projections(self):
        if self.projection_panel.isVisible():
            self._close_projections()
        else:
            self.projection_panel.show()
            h = max(self._projection_splitter_size, 140)
            self._set_split_panel_size(self.projection_panel, h)
            QtCore.QTimer.singleShot(0, self._reapply_projections)
            QtCore.QTimer.singleShot(50, self._reapply_projections)
            _sync_panel_toolbar(self)

    def _close_poincare(self):
        self.poincare_panel.cancel_solve()
        self.scene.remove_poincare_plane()
        self.poincare_panel.hide()
        size = self._close_split_panel(self.poincare_panel)
        if size > 0:
            self._poincare_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_poincare(self):
        if self.poincare_panel.isVisible():
            self._close_poincare()
        else:
            self.poincare_panel.show()
            h = max(self._poincare_splitter_size, 120)
            self._set_split_panel_size(self.poincare_panel, h)
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
        size = self._close_split_panel(self.bifurcation_panel)
        if size > 0:
            self._bifurcation_splitter_size = size
        _sync_panel_toolbar(self)

    def _toggle_bifurcation(self):
        if self.bifurcation_panel.isVisible():
            self._close_bifurcation()
        else:
            config, values = self._get_current_config_and_values()
            if config is None:
                return
            self.bifurcation_panel.set_config(config, values)
            self.bifurcation_panel.show()
            h = max(self._bifurcation_splitter_size, 120)
            self._set_split_panel_size(self.bifurcation_panel, h)
            _sync_panel_toolbar(self)

    def _close_jupyter_console(self):
        self.jupyter_console_panel.hide()
        self._set_jupyter_console_mode(False)
        _sync_panel_toolbar(self)

    def _toggle_jupyter_console(self):
        if self.jupyter_console_panel.isVisible():
            self._close_jupyter_console()
        else:
            self.jupyter_console_panel.ensure_console()
            self.jupyter_console_panel.show()
            self._set_jupyter_console_mode(True)
            _sync_panel_toolbar(self)

    def closeEvent(self, a0):
        self._save_session_on_close()
        self.jupyter_console_panel.shutdown_kernel()
        self.scene.set_orbit_mode(False)
        self.scene.stop_animation()
        self.solver.shutdown()
        super().closeEvent(a0)
