from pyqtgraph.Qt import QtCore, QtWidgets

CONSOLE_PLOT_KINDS = [
    "Axis",
    "Projection",
    "Separation",
    "Separation fit",
    "Radius",
    "Speed",
    "Displacement",
    "Crossings",
]
LIVE_CONSOLE_PLOT_KINDS = {
    "Axis",
    "Projection",
    "Separation",
    "Separation fit",
    "Radius",
    "Speed",
    "Displacement",
}


STATUS_SUMMARIES = (
    ("Fresh", "Fresh"),
    ("Stale", "Stale"),
    ("Solving", "Solving"),
    ("Solve failed", "Error"),
    ("Live", "Live"),
    ("Cleared", "Clear"),
    ("No live", "Live: 0"),
    ("No solution", "No sol"),
)


def _status_summary(text):
    if not text:
        return "Status"

    for prefix, summary in STATUS_SUMMARIES:
        if text.startswith(prefix):
            return summary

    return text.splitlines()[0]


class WorkspacePanel(QtWidgets.QWidget):
    plot_requested = QtCore.pyqtSignal(str, dict)
    live_trace_remove_requested = QtCore.pyqtSignal(str, int)
    live_plot_clear_requested = QtCore.pyqtSignal(str)

    def __init__(self, console_panel, parent=None):
        super().__init__(parent)
        self.console_panel = console_panel

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toolbar = QtWidgets.QWidget()
        self.toolbar.setObjectName("controlPanel")
        toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(6, 6, 6, 4)
        toolbar_layout.setSpacing(6)

        self.status_button = QtWidgets.QToolButton()
        self.status_button.setText("Status")
        self.status_button.setToolTip("No solution")
        self.status_button.setFixedWidth(58)
        self._status_text = ""
        toolbar_layout.addWidget(self.status_button)

        self.plot_kind_combo = QtWidgets.QComboBox()
        self.plot_kind_combo.addItems(CONSOLE_PLOT_KINDS)
        self.plot_kind_combo.currentTextChanged.connect(self._sync_plot_controls)
        toolbar_layout.addWidget(self.plot_kind_combo)

        self.live_button = QtWidgets.QToolButton()
        self.live_button.setText("Live: 0")
        self.live_button.setToolTip("Live traces for the current plot")
        self.live_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.live_button.setMenu(QtWidgets.QMenu(self.live_button))
        toolbar_layout.addWidget(self.live_button)

        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(["x", "y", "z"])
        self.x_axis_combo = QtWidgets.QComboBox()
        self.x_axis_combo.addItems(["x", "y", "z"])
        self.y_axis_combo = QtWidgets.QComboBox()
        self.y_axis_combo.addItems(["x", "y", "z"])
        self.y_axis_combo.setCurrentText("z")
        toolbar_layout.addWidget(self.axis_combo)
        toolbar_layout.addWidget(self.x_axis_combo)
        toolbar_layout.addWidget(self.y_axis_combo)

        self.trajectory_spin = QtWidgets.QSpinBox()
        self.trajectory_spin.setRange(0, 99)
        self.trajectory_spin.setToolTip("Trajectory index")
        toolbar_layout.addWidget(self.trajectory_spin)

        self.separation_a_spin = QtWidgets.QSpinBox()
        self.separation_a_spin.setRange(0, 99)
        self.separation_a_spin.setToolTip("First trajectory")
        self.separation_b_spin = QtWidgets.QSpinBox()
        self.separation_b_spin.setRange(0, 99)
        self.separation_b_spin.setValue(1)
        self.separation_b_spin.setToolTip("Second trajectory")
        self.log_check = QtWidgets.QCheckBox("Log")
        toolbar_layout.addWidget(self.separation_a_spin)
        toolbar_layout.addWidget(self.separation_b_spin)
        toolbar_layout.addWidget(self.log_check)

        self.live_check = QtWidgets.QCheckBox("Live")
        self.live_check.setChecked(True)
        self.live_check.setToolTip("Keep this plot linked to parameter changes")
        self.append_check = QtWidgets.QCheckBox("Overlay")
        self.label_edit = QtWidgets.QLineEdit()
        self.label_edit.setPlaceholderText("Label")
        self.label_edit.setMinimumWidth(130)
        toolbar_layout.addWidget(self.live_check)

        self.return_samples_spin = QtWidgets.QSpinBox()
        self.return_samples_spin.setRange(10, 200000)
        self.return_samples_spin.setValue(2000)
        self.return_samples_spin.setSingleStep(100)
        self.return_samples_spin.setToolTip("Samples used for return analysis")
        self.return_count_spin = QtWidgets.QSpinBox()
        self.return_count_spin.setRange(1, 10000)
        self.return_count_spin.setValue(20)
        self.return_count_spin.setToolTip("Number of return matches")
        self.return_unique_check = QtWidgets.QCheckBox("Unique")
        self.return_unique_check.setChecked(True)
        self.return_unique_check.setToolTip("Keep unique return pairs")

        self.crossing_auto_value_check = QtWidgets.QCheckBox("Auto value")
        self.crossing_auto_value_check.setChecked(True)
        self.crossing_auto_value_check.setToolTip(
            "Use the current default section value"
        )
        self.crossing_value_spin = QtWidgets.QDoubleSpinBox()
        self.crossing_value_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.crossing_value_spin.setDecimals(4)
        self.crossing_value_spin.setSingleStep(0.5)
        self.crossing_value_spin.setEnabled(False)
        self.crossing_value_spin.setToolTip("Manual crossing plane value")
        self.crossing_auto_value_check.toggled.connect(
            lambda checked: self.crossing_value_spin.setEnabled(not checked)
        )
        self.crossing_direction_combo = QtWidgets.QComboBox()
        self.crossing_direction_combo.addItems(["Both", "Positive", "Negative"])
        self.crossing_direction_combo.setToolTip("Crossing direction")

        self.fit_time_range_check = QtWidgets.QCheckBox("Use t range")
        self.fit_time_range_check.setToolTip("Limit the fit by time")
        self.fit_t_min_spin = QtWidgets.QDoubleSpinBox()
        self.fit_t_min_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.fit_t_min_spin.setDecimals(4)
        self.fit_t_min_spin.setToolTip("Fit start time")
        self.fit_t_max_spin = QtWidgets.QDoubleSpinBox()
        self.fit_t_max_spin.setRange(-1_000_000.0, 1_000_000.0)
        self.fit_t_max_spin.setDecimals(4)
        self.fit_t_max_spin.setValue(100.0)
        self.fit_t_max_spin.setToolTip("Fit end time")
        self.fit_time_range_check.toggled.connect(self._sync_fit_option_enabled)

        self.fit_step_range_check = QtWidgets.QCheckBox("Use step range")
        self.fit_step_range_check.setToolTip("Limit the fit by sample step")
        self.fit_step_min_spin = QtWidgets.QSpinBox()
        self.fit_step_min_spin.setRange(0, 1_000_000_000)
        self.fit_step_min_spin.setToolTip("First fit sample step")
        self.fit_step_max_spin = QtWidgets.QSpinBox()
        self.fit_step_max_spin.setRange(0, 1_000_000_000)
        self.fit_step_max_spin.setValue(1000)
        self.fit_step_max_spin.setToolTip("Last fit sample step")
        self.fit_step_range_check.toggled.connect(self._sync_fit_option_enabled)
        self._sync_fit_option_enabled()

        self.options_button = QtWidgets.QToolButton()
        self.options_button.setText("Options")
        self.options_button.setToolTip("Plot options")
        self.options_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.options_menu = self._build_options_menu()
        self.options_button.setMenu(self.options_menu)
        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.clicked.connect(self._emit_plot_request)

        toolbar_layout.addWidget(self.options_button)
        toolbar_layout.addWidget(self.run_button)

        layout.addWidget(self.toolbar)
        layout.addWidget(console_panel, 1)
        self._sync_plot_controls()

    def set_plots(self, names, current_name):
        self.current_plot_name = current_name if current_name in names else ""

    def set_live_traces(self, plot_name, traces):
        count = len(traces)
        self.live_button.setText(f"Live: {count}")
        self.live_button.setEnabled(bool(plot_name))

        menu = QtWidgets.QMenu(self.live_button)
        if not traces:
            action = menu.addAction("No live traces")
            action.setEnabled(False)
        else:
            for trace in traces:
                label = str(trace.get("label") or f"Trace {trace['index'] + 1}")
                mode = str(trace.get("mode") or "full solve")
                action = menu.addAction(f"Remove {label} ({mode})")
                action.setToolTip(f"{label}: {mode}")
                action.triggered.connect(
                    lambda _checked=False, index=trace["index"]: (
                        self.live_trace_remove_requested.emit(plot_name, index)
                    )
                )
            menu.addSeparator()
            clear_action = menu.addAction("Clear live traces")
            clear_action.triggered.connect(
                lambda _checked=False: self.live_plot_clear_requested.emit(plot_name)
            )

        self.live_button.setMenu(menu)

    def _build_options_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.aboutToShow.connect(self._prepare_options_menu)
        widget = QtWidgets.QWidget(menu)
        widget.setMinimumWidth(220)
        self.options_widget = widget
        layout = QtWidgets.QFormLayout(widget)
        self.options_form_layout = layout
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        layout.addRow(self.append_check)
        layout.addRow("Label", self.label_edit)
        layout.addRow("Samples", self.return_samples_spin)
        layout.addRow("Count", self.return_count_spin)
        layout.addRow(self.return_unique_check)
        self.crossing_option_rows = [
            self.crossing_auto_value_check,
            self.crossing_value_spin,
            self.crossing_direction_combo,
        ]
        layout.addRow(self.crossing_auto_value_check)
        layout.addRow("Value", self.crossing_value_spin)
        layout.addRow("Direction", self.crossing_direction_combo)
        self.fit_option_rows = [
            self.fit_time_range_check,
            self.fit_t_min_spin,
            self.fit_t_max_spin,
            self.fit_step_range_check,
            self.fit_step_min_spin,
            self.fit_step_max_spin,
        ]
        layout.addRow(self.fit_time_range_check)
        layout.addRow("t min", self.fit_t_min_spin)
        layout.addRow("t max", self.fit_t_max_spin)
        layout.addRow(self.fit_step_range_check)
        layout.addRow("Step min", self.fit_step_min_spin)
        layout.addRow("Step max", self.fit_step_max_spin)

        action = QtWidgets.QWidgetAction(menu)
        self.options_action = action
        action.setDefaultWidget(widget)
        menu.addAction(action)
        return menu

    def _prepare_options_menu(self):
        self._sync_plot_controls()
        self.options_widget.updateGeometry()
        self.options_widget.adjustSize()
        self.options_menu.updateGeometry()
        self.options_menu.adjustSize()

    def set_solve_state(self, state):
        if state.get("solving"):
            text = "Solving"
        elif state.get("valid"):
            text = "Fresh solution"
        elif state.get("stale"):
            text = "Stale solution"
        elif state.get("last_error"):
            text = "Solve failed"
        else:
            text = "No solution"

        attractor = state.get("attractor")
        n = state.get("n")
        details = []
        if attractor:
            details.append(str(attractor))
        if n:
            details.append(f"N {int(n)}")
        if state.get("last_error"):
            details.append(str(state["last_error"]))

        status = text
        if details:
            status = f"{text}\n" + " | ".join(details)

        self.set_status(status)

    def set_status(self, text):
        self._status_text = str(text)
        self.status_button.setText(_status_summary(self._status_text))
        self.status_button.setToolTip(self._status_text)

    def _sync_plot_controls(self):
        kind = self.plot_kind_combo.currentText()
        is_axis = kind == "Axis"
        is_projection = kind == "Projection"
        is_separation = kind in {"Separation", "Separation fit"}
        uses_axis = is_axis or kind == "Crossings"
        uses_trajectory = (
            is_axis
            or is_projection
            or kind
            in {
                "Crossings",
                "Displacement",
                "Radius",
                "Speed",
            }
        )
        self.axis_combo.setVisible(uses_axis)
        self.x_axis_combo.setVisible(is_projection)
        self.y_axis_combo.setVisible(is_projection)
        self.trajectory_spin.setVisible(uses_trajectory)
        self.separation_a_spin.setVisible(is_separation)
        self.separation_b_spin.setVisible(is_separation)
        self.log_check.setVisible(kind == "Separation")
        show_crossing_options = kind == "Crossings"
        for widget in self.crossing_option_rows:
            self._set_options_row_visible(widget, show_crossing_options)
        show_fit_options = kind == "Separation fit"
        for widget in self.fit_option_rows:
            self._set_options_row_visible(widget, show_fit_options)
        self._sync_fit_option_enabled()

        live_supported = kind in LIVE_CONSOLE_PLOT_KINDS
        self.live_check.setEnabled(live_supported)
        if not live_supported:
            self.live_check.setChecked(False)
        self.live_check.setToolTip(
            "Keep this plot linked to parameter changes"
            if live_supported
            else "This plot runs as a snapshot"
        )

    def _set_options_row_visible(self, widget, visible):
        self.options_form_layout.setRowVisible(widget, visible)
        widget.setVisible(visible)
        label = self.options_form_layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _sync_fit_option_enabled(self):
        use_time = self.fit_time_range_check.isChecked()
        self.fit_t_min_spin.setEnabled(use_time)
        self.fit_t_max_spin.setEnabled(use_time)
        use_steps = self.fit_step_range_check.isChecked()
        self.fit_step_min_spin.setEnabled(use_steps)
        self.fit_step_max_spin.setEnabled(use_steps)

    def _emit_plot_request(self):
        display_kind = self.plot_kind_combo.currentText()
        kind = display_kind.lower().replace(" ", "_")
        options = {
            "live": self.live_check.isChecked(),
            "mode": "overlay" if self.append_check.isChecked() else "replace",
            "label": self.label_edit.text().strip() or None,
        }
        if kind in {"axis", "crossings"}:
            options["axis"] = self.axis_combo.currentText()
            options["trajectory"] = self.trajectory_spin.value()
            if kind == "crossings":
                options["value"] = (
                    None
                    if self.crossing_auto_value_check.isChecked()
                    else self.crossing_value_spin.value()
                )
                options["direction"] = (
                    self.crossing_direction_combo.currentText().lower()
                )
        elif kind == "projection":
            options["x_axis"] = self.x_axis_combo.currentText()
            options["y_axis"] = self.y_axis_combo.currentText()
            options["trajectory"] = self.trajectory_spin.value()
        elif kind == "separation":
            options["a"] = self.separation_a_spin.value()
            options["b"] = self.separation_b_spin.value()
            options["log"] = self.log_check.isChecked()
        elif kind == "separation_fit":
            options["a"] = self.separation_a_spin.value()
            options["b"] = self.separation_b_spin.value()
            options["t_min"] = (
                self.fit_t_min_spin.value()
                if self.fit_time_range_check.isChecked()
                else None
            )
            options["t_max"] = (
                self.fit_t_max_spin.value()
                if self.fit_time_range_check.isChecked()
                else None
            )
            options["step_min"] = (
                self.fit_step_min_spin.value()
                if self.fit_step_range_check.isChecked()
                else None
            )
            options["step_max"] = (
                self.fit_step_max_spin.value()
                if self.fit_step_range_check.isChecked()
                else None
            )
        else:
            options["trajectory"] = self.trajectory_spin.value()

        self.plot_requested.emit(kind, options)
