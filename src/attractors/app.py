from pathlib import Path

import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .bifurcation_panel import BifurcationPanel
from .control_panel import ControlPanel
from .poincare_panel import PoincarePanel
from .projection_panel import ProjectionPanel
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
from .registry import ATTRACTORS
from .session import clear_session, load_session, save_session, session_settings
from .view_manager import DEFAULT_GRID_HALF_SIZE, ViewManager
from .solve_manager import SolveManager
from .solution_validation import validate_solutions
from .style import SPLITTER_HANDLE

WINDOW_SIZE = 1100
PARTIAL_N = 40000
PROJECTION_UPDATE_INTERVAL_MS = 100
MAIN_VIEW_MARGIN = 8


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
    return list(ATTRACTORS.keys())[0]


def _can_restore_builtin_session(state):
    return state.get("attractor") in ATTRACTORS


def _can_restore_session(state):
    return _can_restore_builtin_session(state) or state.get("attractor") == "Custom"


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        self._initial_full_solves = 0
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self._active_solve_request_id = None
        self._active_lyapunov_request_id = None
        self._last_projection_update_ms = None
        self._latest_projection_solutions = None
        self._settings = session_settings()
        self._session_state = load_session(self._settings)
        self._session_reset_requested = False
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

        self.scene = ViewManager(self)
        self.scene.animation_finished.connect(self._on_anim_finished)
        self.scene.projections_data.connect(self._on_projections_data)

        self.controls = ControlPanel()
        self.controls.attractor_changed.connect(self.on_attractor_change)
        self.controls.solve_requested.connect(self._on_controls_solve_requested)
        self.controls.projections_requested.connect(self._toggle_projections)
        self.controls.bifurcation_requested.connect(self._toggle_bifurcation)
        self.controls.poincare_requested.connect(self._toggle_poincare)
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

        self.projection_panel = ProjectionPanel()
        self.projection_panel.close_requested.connect(self._close_projections)
        self.projection_panel.hide()

        self._projection_splitter_size = 260

        self.bifurcation_panel = BifurcationPanel()
        self.bifurcation_panel.close_requested.connect(self._close_bifurcation)
        self.bifurcation_panel.hide()

        self._bifurcation_splitter_size = 500

        self.inner_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.inner_splitter.addWidget(self.scene.container)
        self.inner_splitter.addWidget(self.projection_panel)
        self.inner_splitter.addWidget(self.poincare_panel)
        self.inner_splitter.addWidget(self.bifurcation_panel)
        self.inner_splitter.setSizes([600, 0, 0, 0])
        self.inner_splitter.setStyleSheet(SPLITTER_HANDLE)

        main_area = QtWidgets.QWidget()
        main_area_layout = QtWidgets.QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(
            0,
            MAIN_VIEW_MARGIN,
            MAIN_VIEW_MARGIN,
            MAIN_VIEW_MARGIN,
        )
        main_area_layout.addWidget(self.inner_splitter)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(self.controls)
        splitter.addWidget(main_area)
        splitter.setSizes([int(WINDOW_SIZE * 0.3), int(WINDOW_SIZE * 0.7)])
        splitter.setStyleSheet(SPLITTER_HANDLE)
        layout.addWidget(splitter)

        self.scene.container.installEventFilter(self)

        self.scene.build_grid(DEFAULT_GRID_HALF_SIZE)
        self._refresh_presets()
        self.controls.set_current_attractor(self.current_name)
        self._rebuild_view(self.current_name)
        self._restore_session(self._session_state)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize:
            if obj is self.scene.container:
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
        self.controls.hide_standard_controls()
        if self._custom_config is not None:
            self._apply_config_to_view(self._custom_config)

    def _rebuild_view_from_config(self, config):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self.scene.set_info(config, self.controls.get_current_values())
        self.scene.set_camera(config)
        self.controls.configure(config)
        self.current_n = config.time_defaults["n"]
        self.current_t_max = config.time_defaults["t_max"]
        self.controls.set_traj_tail_max(self.current_n)
        self.scene.clear_lyapunov()
        self.controls.trajectory_panel.reset(config)
        self.bifurcation_panel.set_config(config, self.controls.get_current_values())
        self._update_plot()

    def _on_custom_compile(self, config):
        self._custom_config = config
        self.current_name = "Custom"
        self.controls.set_current_attractor("Custom")
        self._apply_config_to_view(config)

    def _apply_loaded_preset(self, config, values, n, t_max):
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
        self.scene.set_camera(config)
        self.controls.configure(config)
        self.controls.set_current_values(values)
        self.controls.set_time_values(n, t_max)
        self.current_n = n
        self.current_t_max = t_max
        self.controls.set_traj_tail_max(self.current_n)
        self.scene.set_info(config, self.controls.get_current_values())
        self.scene.clear_lyapunov()
        self.controls.trajectory_panel.reset(config)
        self.bifurcation_panel.set_config(config, self.controls.get_current_values())
        self._update_plot()

    def _collect_session_state(self):
        values = self.controls.get_current_values()
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
            "visual_options": self.controls.get_visual_options(),
            "panels": {
                "projections": self.projection_panel.isVisible(),
                "poincare": self.poincare_panel.isVisible(),
                "bifurcation": self.bifurcation_panel.isVisible(),
            },
            "camera": self.scene.get_camera_state(),
            "selected_preset": self.controls.current_preset_name(),
        }

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
            self._custom_config = config
            self.current_name = "Custom"
            self.controls.set_current_attractor("Custom")
            self.controls.hide_standard_controls()
            self.scene.stop_animation()
            self.controls.set_anim_playing(False)
            self.scene.set_camera(config)
            self.controls.configure(config)
            self.controls.custom_panel.set_from_config(config)
            self.controls.set_current_values(state.get("values", {}))
            self.scene.clear_lyapunov()
            self.controls.trajectory_panel.reset(config)
            self.bifurcation_panel.set_config(
                config, self.controls.get_current_values()
            )

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

        selected_preset = state.get("selected_preset")
        if selected_preset:
            self._refresh_presets(str(selected_preset))

        panels = state.get("panels", {})
        if isinstance(panels, dict):
            if panels.get("projections"):
                self._toggle_projections()
            if panels.get("poincare"):
                self._toggle_poincare()
            if panels.get("bifurcation"):
                self._toggle_bifurcation()

        self._update_plot()

        camera = state.get("camera")
        if isinstance(camera, dict):
            self.scene.set_camera_state(camera)

    def _refresh_presets(self, selected=None):
        self.controls.set_saved_presets(list_presets(self._preset_directory), selected)
        self._update_preset_summary(selected or self.controls.current_preset_name())

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

    def _update_plot(self):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
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
        user_n = self.current_n or config.time_defaults["n"]
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

    def _on_controls_solve_requested(self, full):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
        self.solver.cancel_solve()
        self._solve_pending = False
        self._solve_needed = full
        self._full_needed = full
        self._dispatch_solve(full=full)

    def _on_solve_result(self, request_id, solutions, is_partial):
        if request_id != self._active_solve_request_id:
            if is_partial and solutions is not None:
                is_valid, _ = validate_solutions(solutions)
                if is_valid:
                    self.scene.display_solutions(solutions, is_partial)
                    self.scene.refresh_colours()
            return

        self._solve_pending = False

        if solutions is None:
            if self._solve_needed:
                self._solve_needed = False
                self._dispatch_solve(full=self._full_needed)
            else:
                self.controls.set_status("Solve failed", error=True)
            return

        is_valid, message = validate_solutions(solutions)
        if not is_valid:
            self.controls.set_status(message, error=True)
            if self._solve_needed:
                self._solve_needed = False
                full = self._full_needed
                self._full_needed = False
                self._dispatch_solve(full=full)
            return

        self.controls.clear_status()
        self.scene.display_solutions(solutions, is_partial)

        if not is_partial:
            self._latest_projection_solutions = solutions
            config, values = self._get_current_config_and_values()
            if config is not None:
                if self.poincare_panel.isVisible():
                    self.poincare_panel.set_attractor(config, values)
                self.controls.set_status("Computing Lyapunov spectrum")
                self._active_lyapunov_request_id = self.solver.request_lyapunov(
                    config, values
                )
            self._update_projection_panel_from_solutions(solutions)
            if self.projection_panel.isVisible() and self._initial_full_solves == 0:
                QtCore.QTimer.singleShot(0, self._reapply_projections)
                self._initial_full_solves += 1
            self.scene.auto_adjust_grid(solutions)

        self.scene.refresh_colours()

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
        self.projection_panel.update_projections(x, y, z)
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
        self.projection_panel.update_projections(x, y, z)

    def _reset_camera(self):
        config, _ = self._get_current_config_and_values()
        if config is not None:
            self.scene.set_camera(config)

    def _on_anim_toggled(self):
        playing = self.scene.toggle_animation()
        self.controls.set_anim_playing(playing)

    def _on_anim_finished(self):
        self.controls.set_anim_playing(False)

    def _on_n_changed(self, val):
        self.current_n = val
        self.controls.set_traj_tail_max(val)

    def _on_t_max_changed(self, val):
        self.current_t_max = val

    def _on_trajectories_changed(self, trajectories):
        self.scene.set_trajectories(trajectories)
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _on_trajectory_styles_changed(self, trajectories):
        self.scene.set_trajectories(trajectories)
        self.scene.refresh_colours()

    def _on_lyapunov_result(self, request_id, lyap, ky_dim, t_hist, lyap_hist):
        if request_id != self._active_lyapunov_request_id:
            return

        self.scene.set_lyapunov_result(lyap, ky_dim, t_hist, lyap_hist)
        self.controls.clear_status()

    def _close_projections(self):
        self.projection_panel.hide()
        sizes = self.inner_splitter.sizes()
        idx = self.inner_splitter.indexOf(self.projection_panel)
        if idx >= 0:
            self._projection_splitter_size = sizes[idx]
            sizes[idx] = 0
        self.inner_splitter.setSizes(sizes)

    def _toggle_projections(self):
        if self.projection_panel.isVisible():
            self._close_projections()
        else:
            self.projection_panel.show()
            sizes = self.inner_splitter.sizes()
            total = sum(sizes)
            h = max(self._projection_splitter_size, 140)
            idx = self.inner_splitter.indexOf(self.projection_panel)
            sizes[0] = max(total - h, 100)
            sizes[idx] = h
            self.inner_splitter.setSizes(sizes)
            QtCore.QTimer.singleShot(0, self._reapply_projections)
            QtCore.QTimer.singleShot(50, self._reapply_projections)

    def _close_poincare(self):
        self.poincare_panel.cancel_solve()
        self.scene.remove_poincare_plane()
        self.poincare_panel.hide()
        sizes = self.inner_splitter.sizes()
        idx = self.inner_splitter.indexOf(self.poincare_panel)
        if idx >= 0:
            self._poincare_splitter_size = sizes[idx]
            sizes[idx] = 0
        self.inner_splitter.setSizes(sizes)

    def _toggle_poincare(self):
        if self.poincare_panel.isVisible():
            self._close_poincare()
        else:
            self.poincare_panel.show()
            sizes = self.inner_splitter.sizes()
            total = sum(sizes)
            h = max(self._poincare_splitter_size, 120)
            idx = self.inner_splitter.indexOf(self.poincare_panel)
            sizes[0] = max(total - h, 100)
            sizes[idx] = h
            self.inner_splitter.setSizes(sizes)
            self.scene.set_poincare_plane(
                self.poincare_panel.plane_combo.currentText(),
                self.poincare_panel.value_spin.value(),
            )
            self.poincare_panel.recompute()
            config, values = self._get_current_config_and_values()
            if config is not None:
                self.poincare_panel.set_attractor(config, values)

    def _close_bifurcation(self):
        self.bifurcation_panel.cancel_sweep()
        self.bifurcation_panel.hide()
        sizes = self.inner_splitter.sizes()
        idx = self.inner_splitter.indexOf(self.bifurcation_panel)
        if idx >= 0:
            self._bifurcation_splitter_size = sizes[idx]
            sizes[idx] = 0
        self.inner_splitter.setSizes(sizes)

    def _toggle_bifurcation(self):
        if self.bifurcation_panel.isVisible():
            self._close_bifurcation()
        else:
            config, values = self._get_current_config_and_values()
            if config is None:
                return
            self.bifurcation_panel.set_config(config, values)
            self.bifurcation_panel.show()
            sizes = self.inner_splitter.sizes()
            total = sum(sizes)
            h = max(self._bifurcation_splitter_size, 120)
            idx = self.inner_splitter.indexOf(self.bifurcation_panel)
            sizes[0] = max(total - h, 100)
            sizes[idx] = h
            self.inner_splitter.setSizes(sizes)

    def closeEvent(self, a0):
        self._save_session_on_close()
        self.scene.set_orbit_mode(False)
        self.scene.stop_animation()
        self.solver.shutdown()
        super().closeEvent(a0)
