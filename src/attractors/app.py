import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

from .bifurcation_dialog import BifurcationDialog
from .control_panel import ControlPanel
from .poincare_dialog import PoincareSectionDialog
from .registry import ATTRACTORS
from .view_manager import ViewManager
from .solve_manager import SolveManager
from .style import SPLITTER

WINDOW_SIZE = 1100
PARTIAL_N = 40000


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        self._initial_full_solves = 0
        self._solve_pending = False
        self._solve_needed = False
        self._full_needed = False
        self.current_n = 100000
        self.current_t_max = 50
        self.current_name = list(ATTRACTORS.keys())[0]
        self._custom_config = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.solver = SolveManager(self)
        self.solver.solutions_ready.connect(self._on_solve_result)
        self.solver.lyapunov_ready.connect(self._on_lyapunov_result)

        self.scene = ViewManager(self)
        self.scene.animation_finished.connect(self._on_anim_finished)
        self.scene.trajectories_changed.connect(self._on_trajectories_changed)
        self.scene.styles_changed.connect(self._on_trajectory_styles_changed)
        self.scene.custom_compiled.connect(self._on_custom_compile)
        self.scene.projections_data.connect(self._on_projections_data)

        self.controls = ControlPanel()
        self.controls.attractor_changed.connect(self.on_attractor_change)
        self.controls.solve_requested.connect(self._on_controls_solve_requested)
        self.controls.bifurcation_requested.connect(self._open_bifurcation)
        self.controls.poincare_requested.connect(self._open_poincare)
        self.controls.n_changed.connect(self._on_n_changed)
        self.controls.t_max_changed.connect(self._on_t_max_changed)
        self.controls.animation_toggled.connect(self._on_anim_toggled)
        self.controls.point_button.toggled.connect(self.scene.set_point_mode)
        self.controls.line_mode.toggled.connect(self.scene.set_line_mode)
        self.controls.trail_mode.toggled.connect(self.scene.set_trail_mode)
        self.controls.show_grid.toggled.connect(self.scene.set_grid_visible)
        self.controls.alpha_slider.valueChanged.connect(self.scene.set_alpha)
        self.controls.alpha_spin.valueChanged.connect(self.scene.set_alpha)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setStyleSheet(SPLITTER)
        splitter.addWidget(self.scene.container)
        splitter.addWidget(self.controls)
        splitter.setSizes([int(WINDOW_SIZE * 0.7), int(WINDOW_SIZE * 0.3)])
        layout.addWidget(splitter)

        self.scene.container.installEventFilter(self)
        self.scene.custom_panel.installEventFilter(self)
        self.scene.trajectory_panel.installEventFilter(self)

        self.scene.build_grid(30.0)
        self._rebuild_view(self.current_name)
        self.scene.reposition_overlays()

    def showEvent(self, event):
        super().showEvent(event)
        self.scene.reposition_overlays()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize:
            if obj in (
                self.scene.container,
                self.scene.custom_panel,
                self.scene.trajectory_panel,
            ):
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
        self.scene.custom_panel.setVisible(True)
        if self._custom_config is not None:
            self._apply_config_to_view(self._custom_config)

    def _rebuild_view_from_config(self, config):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
        self.scene.custom_panel.setVisible(False)
        self.controls.show_standard_controls()
        self._apply_config_to_view(config)

    def _apply_config_to_view(self, config):
        self.scene.set_equation(config.equation_text)
        self.scene.set_camera(config)
        self.controls.configure(config)
        self.current_n = config.time_defaults["n"]
        self.current_t_max = config.time_defaults["t_max"]
        self.scene.clear_lyapunov()
        self.scene.reset_trajectory_panel(config)
        self._update_plot()

    def _on_custom_compile(self, config):
        self._custom_config = config
        self._apply_config_to_view(config)

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
        self._dispatch_solve(full=True)
        config, values = self._get_current_config_and_values()
        if config is not None:
            self.scene.update_status(config, values)

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
        ics = self.scene.get_trajectories()
        ic_list = [t["ic"] for t in ics] if ics else [config.initial_conditions]
        dispatch_n = user_n if full else min(user_n, PARTIAL_N)
        self.solver.request_solve(config, values, ic_list, dispatch_n, not full, t_max)

    def _on_controls_solve_requested(self, full):
        self.scene.stop_animation()
        self.controls.set_anim_playing(False)
        self._solve_needed = True
        self._full_needed = full
        self._dispatch_solve(full=full)

    def _on_solve_result(self, solutions, is_partial):
        self._solve_pending = False

        if solutions is None:
            if self._solve_needed:
                self._solve_needed = False
                self._dispatch_solve(full=self._full_needed)
            return

        self.scene.display_solutions(solutions, is_partial)

        if not is_partial:
            all_sol = np.concatenate(solutions, axis=0)
            x, y, z = all_sol.T
            self.controls.update_projections(x, y, z)
            config, values = self._get_current_config_and_values()
            if config is not None:
                self.solver.request_lyapunov(config, values)
            if self._initial_full_solves == 0:
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
        self.controls.reapply_projections(self.scene.get_solutions())

    def _on_projections_data(self, x, y, z):
        self.controls.update_projections(x, y, z)

    def _on_anim_toggled(self):
        playing = self.scene.toggle_animation()
        self.controls.set_anim_playing(playing)

    def _on_anim_finished(self):
        self.controls.set_anim_playing(False)

    def _on_n_changed(self, val):
        self.current_n = val

    def _on_t_max_changed(self, val):
        self.current_t_max = val

    def _on_trajectories_changed(self, trajectories):
        self._solve_needed = True
        self._full_needed = True
        self._dispatch_solve(full=True)

    def _on_trajectory_styles_changed(self, trajectories):
        self.scene.refresh_colours()

    def _on_lyapunov_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.scene.set_lyapunov_result(lyap, ky_dim, t_hist, lyap_hist)

    def _open_poincare(self):
        sols = self.scene.get_solutions()
        sol = sols[0].copy() if sols else None
        dialog = PoincareSectionDialog(self, sol, self)
        dialog.show()

    def _open_bifurcation(self):
        config, values = self._get_current_config_and_values()
        if config is None:
            return
        dialog = BifurcationDialog(config, values, self)
        dialog.show()

    def closeEvent(self, a0):
        self.scene.stop_animation()
        self.solver.shutdown()
        super().closeEvent(a0)
