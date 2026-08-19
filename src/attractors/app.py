import weakref
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .console.colour import colourmap
from .console.jupyter_console_panel import JupyterConsolePanel
from .console.live_plot_controller import LivePlotController
from .console.system import SystemInspector
from .console.workspace_controller import WorkspaceController
from .console.workspace_inspector import WorkspaceInspector
from .core.solution_validation import validate_solutions
from .perf import PerfProfiler, perf_finish, perf_start
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
from .ui.docking import AreaBoundDock as Dock
from .ui.docking import AreaBoundDockArea as DockArea
from .ui.lyapunov_panel import LyapunovPanel
from .ui.poincare_panel import PoincarePanel
from .ui.process_metrics import ProcessUsageStatus
from .ui.projection_panel import ProjectionPanel
from .ui.right_panel import RightPanel
from .ui.style import SCENE_TOOLBAR, SPLITTER_HANDLE_HOVER
from .ui.system_toolbar import SystemToolbar
from .ui.workspace_panel import WorkspacePanel
from .view.grid_overlay import DEFAULT_GRID_HALF_SIZE
from .view.view_manager import ViewManager
from .workers.solve_manager import SolveManager

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 850
PARTIAL_N = 40000
PROJECTION_UPDATE_INTERVAL = 100  # ms


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


def _workspace_visible(window):
    if window.workspace_dock is not None:
        return window.workspace_dock.container() is not None

    return _panel_visible(window, "jupyter_console_panel")


def app_settings():
    return QtCore.QSettings("Aymen Hafeez", "Systems analysis")


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Systems analysis")

        self.reset_session_state = False

        self._initial_full_solves = 0
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._restoring_view = False
        self._active_solve_request_id = None
        self._active_lyapunov_request_id = None

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
        self._app_status_clear_timer = None
        self._panel_docks = {}
        self._panel_dock_titles = {}
        self._panel_dock_defaults = {}
        self._closing_panel_dock = None
        self._closing_workspace_dock = False
        self._workspace_tab_stacks = weakref.WeakSet()
        self._jupyter_toolbar_actions = []
        self.system_toolbar_action = None
        self._menu_actions = []
        self._left_panel_splitter_size = int(WINDOW_WIDTH * 0.22)
        self._right_panel_splitter_size = int(WINDOW_WIDTH * 0.23)
        self._pre_explore_side_panel_state = None

        self.workspace_dock = None
        self.workspace_mode_combo = None
        self.workspace_system_mode_action = None
        self.workspace_explore_mode_action = None
        self.workspace_mode = "system"
        self._explore_toolbar_actions = []
        self._connected_explorer = None

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

        self.controls = ControlPanel()
        self.right_panel = RightPanel()
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
        self.poincare_panel.hide()

        self.lyapunov_panel = LyapunovPanel()
        self.lyapunov_panel.compute_requested.connect(self._request_lyapunov)
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
        self.system_toolbar = SystemToolbar()
        self.jupyter_console_panel.script_panel.status_changed.connect(
            lambda message: self._set_temporary_app_status(message)
        )
        self.jupyter_console_panel.close_requested.connect(self._close_jupyter_console)

        self.workspace_panel = WorkspacePanel(self.jupyter_console_panel)

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

        self._build_toolbar()
        self._build_menu_bar()
        self._build_status_bar()

        self.workspace_inspector = WorkspaceInspector(self.jupyter_console_panel)

        self.workspace_dock_area = DockArea()
        self.viewport_dock = Dock("Viewport", size=(10, 12))
        self.viewport_dock.addWidget(self.scene.container)
        self.workspace_dock_area.addDock(self.viewport_dock)
        self.workspace_dock = self._build_workspace_dock()
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
            "bifurcation_panel": ("top", self.viewport_dock),
            "projection_panel": ("above", self.viewport_dock),
        }
        self._connect_workspace_dock_signals()

        main_area = QtWidgets.QWidget()
        main_area_layout = QtWidgets.QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(
            0,
            4,
            0,
            4,
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

        self._restore_app_layout()

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

    def _build_toolbar(self):
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
            self.scene.camera_controller.set_orbit_mode,
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

    def _workspace_mode_toolbar_control(self, toolbar):
        self.workspace_mode_combo = QtWidgets.QComboBox()
        self.workspace_mode_combo.setToolTip("Workspace mode")
        self.workspace_mode_combo.addItem("System", "system")
        self.workspace_mode_combo.addItem("Explore", "explore")
        self.workspace_mode_combo.currentIndexChanged.connect(
            lambda _index: self._on_workspace_mode_selected()
        )
        self._jupyter_toolbar_actions.append(
            toolbar.addWidget(self.workspace_mode_combo)
        )

    def _on_workspace_mode_selected(self):
        mode = self.workspace_mode_combo.currentData()
        if mode is not None:
            self._set_workspace_mode(mode)

    def _enter_explore_workspace(self):
        self.jupyter_console_panel.ensure_console()
        self._open_workspace_dock()
        self.jupyter_console_panel.apply_explore_layout()

    def _restore_explore_layout(self):
        self._set_workspace_mode("explore")
        self.jupyter_console_panel.apply_explore_layout()
        self._set_temporary_app_status("Restored Explore layout")

    def _set_workspace_mode(self, mode):
        key = str(mode).strip().lower()
        self.workspace_mode = key
        self._workspace_focus(key)

        if key == "explore":
            self._enter_explore_workspace()

        self.workspace_panel.set_mode(key)
        self._sync_jupyter_workspace_state()
        self._sync_explore_actions()

        # sync workspace mode controls
        if self.workspace_mode_combo is not None:
            index = self.workspace_mode_combo.findData(key)
            if index >= 0 and self.workspace_mode_combo.currentIndex() != index:
                with QtCore.QSignalBlocker(self.workspace_mode_combo):
                    self.workspace_mode_combo.setCurrentIndex(index)

        if (
            self.workspace_system_mode_action is not None
            and self.workspace_explore_mode_action is not None
        ):
            with (
                QtCore.QSignalBlocker(self.workspace_system_mode_action),
                QtCore.QSignalBlocker(self.workspace_explore_mode_action),
            ):
                self.workspace_system_mode_action.setChecked(key == "system")
                self.workspace_explore_mode_action.setChecked(key == "explore")

        self._sync_menu_actions()

    def _workspace_focus(self, mode):
        if mode == "explore":
            if self._pre_explore_side_panel_state is None:
                self._pre_explore_side_panel_state = {
                    "left": self.controls.isVisible(),
                    "right": self.right_panel.isVisible(),
                }
            self._set_side_panel_actions(left=False, right=False)
            return

        if mode == "system" and self._pre_explore_side_panel_state is not None:
            state = self._pre_explore_side_panel_state
            self._pre_explore_side_panel_state = None
            self._set_side_panel_actions(left=state["left"], right=state["right"])

    def _current_explorer(self):
        return self.jupyter_console_panel.plots.current.explore

    def _set_side_panel_actions(self, *, left, right):
        with (
            QtCore.QSignalBlocker(self.toolbar_left_panel_action),
            QtCore.QSignalBlocker(self.toolbar_right_panel_action),
        ):
            self.toolbar_left_panel_action.setChecked(bool(left))
            self.toolbar_right_panel_action.setChecked(bool(right))
        self._set_left_panel_visible(left)
        self._set_right_panel_visible(right)
        self._sync_menu_actions()

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
        source_action.changed.connect(
            lambda action=action, source_action=source_action: self._sync_menu_action(
                action, source_action
            )
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

    def _build_menu_bar(self):
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
        self._add_menu_action(
            view_menu, "Status bar", self.toolbar_process_status_action
        )
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
        view_menu.addAction("Reset session state", self._reset_session_state)

        system_menu = menu_bar.addMenu("&System")
        system_menu.addAction("Solve", lambda: self._on_controls_solve_requested(True))
        system_menu.addAction(
            "Reset parameters",
            self.controls.reset_to_defaults,
        )
        system_menu.addSeparator()
        self._add_menu_action(system_menu, "Loop animation", self.toolbar_loop_action)
        self._add_menu_action(
            system_menu, "Show leading point", self.toolbar_point_action
        )
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
        workspace_menu.addSeparator()

        workspace_menu.addAction("Workspace help", lambda: self.system.help(table=True))

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
        dock = Dock(title, size=(10, 12), closable=True)
        dock.addWidget(panel)
        dock.sigClosed.connect(lambda _dock: self._on_panel_dock_closed(panel))
        return dock

    def _build_workspace_dock(self):
        dock = Dock("Workspace", size=(10, 12), closable=True)
        dock.addWidget(self.workspace_panel)
        dock.sigClosed.connect(lambda _dock: self._on_workspace_dock_closed())

        return dock

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
            self.toolbar_jupyter_console_action.setChecked(_workspace_visible(self))
            self.toolbar_process_status_action.setChecked(self._process_status_visible)
        self._sync_menu_actions()
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
        self._sync_menu_actions()

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

        self.plot_view_all_action = QtGui.QAction(
            self._toolbar_icon(
                "zoom-fit-best",
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton,
            ),
            "View all",
            self,
        )
        self.plot_view_all_action.setToolTip("Fit all plot data")
        self.plot_view_all_action.triggered.connect(view_box.autoRange)

        mouse_group = QtGui.QActionGroup(self)
        mouse_group.setExclusive(True)
        self.plot_pan_action = QtGui.QAction(
            self._toolbar_icon(
                "transform-move",
                QtWidgets.QStyle.StandardPixmap.SP_ArrowUp,
            ),
            "Pan",
            self,
        )
        self.plot_pan_action.setCheckable(True)
        self.plot_pan_action.setChecked(True)
        self.plot_pan_action.setToolTip("Pan with left mouse button")
        self.plot_zoom_action = QtGui.QAction(
            self._toolbar_icon(
                "zoom-in",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
            ),
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

        self._workspace_mode_toolbar_control(toolbar)
        self._add_jupyter_plot_controls(toolbar)
        self.plot_options_menu = plot_item.getMenu()
        self.plot_view_menu = view_box.menu

        for action in self._jupyter_toolbar_actions:
            action.setVisible(False)

    def _add_jupyter_plot_controls(self, toolbar):
        label = QtWidgets.QLabel("View")
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
            # (
            #     "New",
            #     "list-add",
            #     QtWidgets.QStyle.StandardPixmap.SP_FileIcon,
            #     lambda: self._new_live_plot(),
            #     "Create a new workspace view",
            # ),
            (
                "Rename",
                "edit-rename",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                lambda: self.workspace_controller.rename_current_view(),
                "Rename the current workspace view",
            ),
            (
                "Clear",
                "edit-clear-history",
                QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton,
                lambda: self.workspace_controller.clear_current_view(),
                "Clear the current view",
            ),
            (
                "Clear all",
                "edit-delete",
                QtWidgets.QStyle.StandardPixmap.SP_TrashIcon,
                lambda: self.workspace_controller.clear_all_views(),
                "Clear all views",
            ),
            (
                "Fit",
                "view-fullscreen",
                # QtGui.QIcon.fromTheme("view-fullscreen"),
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton,
                lambda: self.workspace_controller.fit_current_view(),
                "Fit current view",
            ),
            (
                "Reset",
                "zoom-original",
                # QtGui.QIcon.fromTheme("zoom-original"),
                QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
                lambda: self.workspace_controller.reset_current_view(),
                "Reset camera",
            ),
        ]

        new_button = QtWidgets.QToolButton()
        new_button.setText("New")
        new_button.setIcon(
            self._toolbar_icon(
                "list-add", QtWidgets.QStyle.StandardPixmap.SP_FileDialogNewFolder
            )
        )
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

        for text, theme_name, fallback_icon, callback, tooltip in icon_specs:
            action = toolbar.addAction(
                self._toolbar_icon(theme_name, fallback_icon),
                text,
            )
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            self._jupyter_toolbar_actions.append(action)
            self._keep_toolbar_action_from_taking_focus(toolbar, action)
        self.workspace_controller.sync_views()
        self._keep_toolbar_action_from_taking_focus(toolbar, new_action)

        self.workspace_grid_action = toolbar.addAction(
            self._toolbar_icon(
                "view-grid", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView
            ),
            "Grid",
        )
        self.workspace_grid_action.setCheckable(True)
        self.workspace_grid_action.setChecked(True)
        self.workspace_grid_action.setToolTip("Toggle grid visibility")
        self.workspace_grid_action.toggled.connect(
            self.workspace_controller.set_current_grid_visible
        )
        self._jupyter_toolbar_actions.append(self.workspace_grid_action)
        self._keep_toolbar_action_from_taking_focus(toolbar, self.workspace_grid_action)
        self.workspace_controller.sync_grid_action()

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
            self._toolbar_icon(
                "edit-clear", QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton
            ),
            "Sliders",
            self._clear_current_explore_sliders,
        )
        self.explore_clear_sliders_action.setToolTip(
            "Clear sliders for the current view"
        )

        self.explore_clear_state_action = toolbar.addAction(
            self._toolbar_icon(
                "edit-delete", QtWidgets.QStyle.StandardPixmap.SP_TrashIcon
            ),
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

        self.explore_trace_button.setText(f"Traces: {len(trace_names)}")
        self.explore_clear_sliders_action.setEnabled(bool(slider_names))
        self.explore_clear_state_action.setEnabled(bool(trace_names or slider_names))

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
        for source_action in source_menu.actions():
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
        if self.workspace_dock is not None:
            visible = self.workspace_dock.container() is not None
            if visible:
                item = self.workspace_dock
                container = item.container()
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
                            visible = False
                            break
                    item = container
                    try:
                        container = container.container()
                    except AttributeError:
                        container = None
        else:
            visible = _workspace_visible(self)

        for action in self._jupyter_toolbar_actions:
            action.setVisible(visible)

        if self.system_toolbar_action is not None:
            self.system_toolbar_action.setVisible(
                visible and self.workspace_mode == "system"
            )

        self._sync_explore_actions()

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

    def _set_solve_state(self, **updates):
        state = dict(self._solve_state)
        state.update(updates)
        self._solve_state = state
        self.system_toolbar.set_solve_state(state)

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
        if trajectories:
            trajectory_specs = []
            for trajectory in trajectories:
                trajectory_n = int(trajectory.get("n", user_n))
                solve_n = trajectory_n if full else min(trajectory_n, PARTIAL_N)
                trajectory_specs.append(
                    {
                        "ic": [float(coord) for coord in trajectory["ic"]],
                        "n": solve_n,
                        "t_max": float(trajectory.get("t_max", t_max)),
                    }
                )
        else:
            solve_n = int(user_n if full else min(user_n, PARTIAL_N))
            trajectory_specs = [
                {
                    "ic": [float(coord) for coord in config.initial_conditions],
                    "n": solve_n,
                    "t_max": float(t_max),
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
        self._active_solve_request_id = self.solver.request_solve(
            config, values, trajectory_specs, dispatch_n, not full, dispatch_t_max
        )
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
            solution_points=[len(solution) for solution in solutions or []],
        )

        if is_partial:
            self.live_plot_controller._refresh_live_preview(solutions)
            self._update_projection_panel_from_solutions(solutions)

        if not is_partial:
            self._last_live_preview_update = None
            self._latest_projection_solutions = solutions
            config, values = self._get_current_config_and_values()
            if config is not None:
                if _panel_visible(self, "poincare_panel"):
                    self.poincare_panel.set_attractor(config, values)
                if (
                    self.lyapunov_panel.isVisible()
                    and self.lyapunov_panel.auto_enabled()
                ):
                    self._request_lyapunov(config, values)
            self._update_projection_panel_from_solutions(solutions)
            if (
                _panel_visible(self, "projection_panel")
                and self._initial_full_solves == 0
            ):
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1
            self.scene.grid_overlay.auto_adjust_grid(solutions)
            for plot_name in list(self.live_plot_controller.live_plots):
                self.live_plot_controller._refresh_live_plot(plot_name)

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
        self._last_projection_update = QtCore.QDateTime.currentMSecsSinceEpoch()

    def _on_projections_data(self, x, y, z):
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

    def _find_dock(self, panel):
        for dock in self._panel_docks.values():
            if panel in dock.widgets:
                return dock

        return None

    def _connect_workspace_dock_signals(self):
        docks = [self.viewport_dock, self.workspace_dock]
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

    def _open_workspace_dock(self):
        self.jupyter_console_panel.ensure_console()

        if self.workspace_dock is None:
            self.workspace_panel.show()
            return

        if self.workspace_dock.container() is None:
            self.workspace_dock_area.addDock(
                self.workspace_dock,
                position="above",
                relativeTo=self.viewport_dock,
            )
        self.workspace_panel.show()
        if self.workspace_dock.container() is not None:
            try:
                self.workspace_dock.raiseDock()
            except AttributeError:
                pass
        self._sync_jupyter_workspace_state()

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
        dock = self._find_dock(panel)
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
        panel_name = None
        dock = None
        for candidate_name, candidate_dock in self._panel_docks.items():
            if panel in candidate_dock.widgets:
                panel_name = candidate_name
                dock = candidate_dock
                break
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

    def _on_workspace_dock_closed(self):
        if not self._closing_workspace_dock:
            self.workspace_panel.hide()
        dock = self._build_workspace_dock()
        dock.container_changed.connect(self._on_workspace_layout_changed)
        self.workspace_dock = dock
        self._sync_jupyter_workspace_state()
        self._sync_toolbar_panel_actions()

    def _close_jupyter_console(self):
        if (
            self.workspace_dock is not None
            and self.workspace_dock.container() is not None
        ):
            self._closing_workspace_dock = True
            try:
                self.workspace_dock.close()
            finally:
                self._closing_workspace_dock = False
        self.workspace_panel.hide()
        self._sync_jupyter_workspace_state()
        self._sync_toolbar_panel_actions()

    def _toggle_jupyter_console(self):
        if _workspace_visible(self):
            self._close_jupyter_console()
        else:
            self.jupyter_console_panel.ensure_console()
            self._open_workspace_dock()
            self.jupyter_console_panel.focus_console()
            self._sync_jupyter_workspace_state()
            self._sync_toolbar_panel_actions()

    def _panel_widget(self, panel_name):
        panels = {
            "lyapunov_panel": self.lyapunov_panel,
            "projection_panel": self.projection_panel,
            "poincare_panel": self.poincare_panel,
            "bifurcation_panel": self.bifurcation_panel,
        }

        return panels[panel_name]

    def _save_workspace_shell(self, settings):
        kind, name = self.jupyter_console_panel.active_view_key()
        script_path = self.jupyter_console_panel.script_panel.current_script_path()
        settings.setValue("workspace/plots", self.jupyter_console_panel.plots.names())
        settings.setValue(
            "workspace/views3d", self.jupyter_console_panel.views3d.names()
        )
        settings.setValue("workspace/tables", self.jupyter_console_panel.tables.names())
        settings.setValue("workspace/active_kind", kind)
        settings.setValue("workspace/active_name", name)

        if script_path is not None:
            settings.setValue("workspace/current_script", str(script_path))
        else:
            settings.remove("workspace/current_script")

    def _restore_workspace_shell(self, settings):
        plot_names = settings.value("workspace/plots", [], type=list)
        view_names = settings.value("workspace/views3d", [], type=list)
        table_names = settings.value("workspace/tables", [], type=list)

        for name in plot_names:
            if name != "Plot":
                self.jupyter_console_panel.plots.new(name, activate=False)

        for name in view_names:
            if name != "3D View":
                self.jupyter_console_panel.views3d.new(name, activate=False)

        for name in table_names:
            if name != "Table":
                self.jupyter_console_panel.tables.new(name, activate=False)

        kind = settings.value("workspace/active_kind", "plot")
        name = settings.value("workspace/active_name", "Plot")

        try:
            self.jupyter_console_panel.set_active_workspace_view(kind, name)
        except (KeyError, ValueError):
            pass

        script_path = settings.value("workspace/current_script")
        self.jupyter_console_panel.script_panel.restore_script(script_path)

    def _save_app_layout(self):
        settings = app_settings()
        settings.setValue("layout/window_geometry", self.saveGeometry())
        settings.setValue("layout/main_splitter", self.main_splitter.saveState())
        settings.setValue("layout/workspace_mode", self.workspace_mode)

        side_state = self._pre_explore_side_panel_state
        if side_state is None:
            side_state = {
                "left": self.controls.isVisible(),
                "right": self.right_panel.isVisible(),
            }

        settings.setValue("layout/left_panel_visible", side_state["left"])
        settings.setValue("layout/right_panel_visible", side_state["right"])
        settings.setValue("layout/workspace_visible", _workspace_visible(self))

        for panel_name in self._panel_docks:
            settings.setValue(
                f"layout/panels/{panel_name}",
                _panel_visible(self, panel_name),
            )

        self._save_workspace_shell(settings)

    def _restore_app_layout(self):
        settings = app_settings()

        geometry = settings.value("layout/window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        splitter = settings.value("layout/main_splitter")
        if splitter is not None:
            self.main_splitter.restoreState(splitter)

        left_visible = settings.value("layout/left_panel_visible", True, type=bool)
        right_visible = settings.value("layout/right_panel_visible", True, type=bool)
        self._pre_explore_side_panel_state = None
        self._set_side_panel_actions(left=left_visible, right=right_visible)

        self._restore_workspace_shell(settings)

        for panel_name in self._panel_docks:
            visible = settings.value(f"layout/panels/{panel_name}", False, type=bool)
            panel = self._panel_widget(panel_name)
            if visible:
                self._open_panel_dock(panel, panel_name)
            else:
                self._close_panel_dock(panel)

        workspace_visible = settings.value("layout/workspace_visible", False, type=bool)
        if workspace_visible:
            self._open_workspace_dock()
        else:
            self._close_jupyter_console()

        mode = settings.value("layout/workspace_mode", "system")
        if mode in {"system", "explore"}:
            self._set_workspace_mode(mode)

        self._sync_toolbar_panel_actions()
        self.workspace_controller.sync_views()

    def _reset_session_state(self):
        settings = app_settings()
        settings.remove("layout")
        settings.remove("workspace")
        settings.sync()

        self.reset_session_state = True
        self._set_temporary_app_status("Reset session state for next launch")

    def closeEvent(self, a0):
        self.jupyter_console_panel.shutdown_kernel()
        self.scene.camera_controller.set_orbit_mode(False)
        self.scene.animation_controller.stop()
        self.solver.shutdown()

        if not self.reset_session_state:
            self._save_app_layout()

        super().closeEvent(a0)
