from pyqtgraph.Qt import QtCore, QtWidgets

STATUS_BUTTON_WIDTH = 58
CONSOLE_PLOT_KINDS = [
    "Axis",
    "Projection",
    "Separation",
    "Separation fit",
    "Radius",
    "Speed",
    "Displacement",
    "Crossings",
    "Returns",
    "Return lags",
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


class _StatusButton:
    def __init__(self, button):
        self._button = button
        self._text = ""

    def setText(self, text):
        self._text = str(text)
        summary = self._summary(self._text)
        self._button.setText(summary)
        self._button.setToolTip(self._text)

    def text(self):
        return self._text

    def _summary(self, text):
        if text.startswith("Fresh"):
            return "Fresh"
        if text.startswith("Stale"):
            return "Stale"
        if text.startswith("Solving"):
            return "Solving"
        if text.startswith("Solve failed"):
            return "Error"
        if text.startswith("Following"):
            return "Live"
        if text.startswith("Cleared"):
            return "Clear"
        if text.startswith("No live"):
            return "Live: 0"
        if text.startswith("No solution"):
            return "No sol"
        if not text:
            return "Status"
        return text.splitlines()[0]


class LabPanel(QtWidgets.QWidget):
    follow_requested = QtCore.pyqtSignal(str, dict)
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
        self.status_button.setFixedWidth(STATUS_BUTTON_WIDTH)
        self.status_label = _StatusButton(self.status_button)

        self.follow_kind_combo = QtWidgets.QComboBox()
        self.follow_kind_combo.addItems(CONSOLE_PLOT_KINDS)
        self.follow_kind_combo.currentTextChanged.connect(self._sync_follow_controls)

        self.live_button = QtWidgets.QToolButton()
        self.live_button.setText("Live: 0")
        self.live_button.setToolTip("Live traces for the current plot")
        self.live_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.live_button.setMenu(QtWidgets.QMenu(self.live_button))

        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(["x", "y", "z"])
        self.x_axis_combo = QtWidgets.QComboBox()
        self.x_axis_combo.addItems(["x", "y", "z"])
        self.y_axis_combo = QtWidgets.QComboBox()
        self.y_axis_combo.addItems(["x", "y", "z"])
        self.y_axis_combo.setCurrentText("z")

        self.trajectory_spin = QtWidgets.QSpinBox()
        self.trajectory_spin.setRange(0, 99)
        self.trajectory_spin.setToolTip("Trajectory index")

        self.separation_a_spin = QtWidgets.QSpinBox()
        self.separation_a_spin.setRange(0, 99)
        self.separation_a_spin.setToolTip("First trajectory")
        self.separation_b_spin = QtWidgets.QSpinBox()
        self.separation_b_spin.setRange(0, 99)
        self.separation_b_spin.setValue(1)
        self.separation_b_spin.setToolTip("Second trajectory")
        self.log_check = QtWidgets.QCheckBox("Log")

        self.append_check = QtWidgets.QCheckBox("Append")
        self.label_edit = QtWidgets.QLineEdit()
        self.label_edit.setPlaceholderText("Label")
        self.label_edit.setMinimumWidth(130)

        self.return_samples_spin = QtWidgets.QSpinBox()
        self.return_samples_spin.setRange(10, 200000)
        self.return_samples_spin.setValue(2000)
        self.return_samples_spin.setSingleStep(100)
        self.return_samples_spin.setToolTip("Samples used for return analysis")
        self.return_min_lag_spin = QtWidgets.QSpinBox()
        self.return_min_lag_spin.setRange(1, 200000)
        self.return_min_lag_spin.setValue(50)
        self.return_min_lag_spin.setToolTip("Minimum lag in samples")
        self.return_count_spin = QtWidgets.QSpinBox()
        self.return_count_spin.setRange(1, 10000)
        self.return_count_spin.setValue(20)
        self.return_count_spin.setToolTip("Number of return matches")
        self.return_unique_check = QtWidgets.QCheckBox("Unique")
        self.return_unique_check.setChecked(True)
        self.return_unique_check.setToolTip("Keep unique return pairs")

        self.crossing_auto_value_check = QtWidgets.QCheckBox("Auto value")
        self.crossing_auto_value_check.setChecked(True)
        self.crossing_auto_value_check.setToolTip("Use the current default section value")
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
        self.follow_button = QtWidgets.QPushButton("Run")
        self.follow_button.clicked.connect(self._emit_follow)

        toolbar_layout.addWidget(self.status_button)
        toolbar_layout.addWidget(self.follow_kind_combo)
        toolbar_layout.addWidget(self.live_button)
        toolbar_layout.addWidget(self.axis_combo)
        toolbar_layout.addWidget(self.x_axis_combo)
        toolbar_layout.addWidget(self.y_axis_combo)
        toolbar_layout.addWidget(self.trajectory_spin)
        toolbar_layout.addWidget(self.separation_a_spin)
        toolbar_layout.addWidget(self.separation_b_spin)
        toolbar_layout.addWidget(self.log_check)
        toolbar_layout.addWidget(self.options_button)
        toolbar_layout.addWidget(self.follow_button)

        layout.addWidget(self.toolbar)
        layout.addWidget(console_panel, 1)
        self._sync_follow_controls()

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
        self.return_option_rows = [
            self.return_samples_spin,
            self.return_min_lag_spin,
            self.return_count_spin,
            self.return_unique_check,
        ]
        layout.addRow("Samples", self.return_samples_spin)
        layout.addRow("Min lag", self.return_min_lag_spin)
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
        self._sync_follow_controls()
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

        self.status_label.setText(
            text if not details else f"{text}\n" + " | ".join(details)
        )

    def _sync_follow_controls(self):
        kind = self.follow_kind_combo.currentText()
        is_axis = kind == "Axis"
        is_projection = kind == "Projection"
        is_separation = kind in {"Separation", "Separation fit"}
        uses_axis = is_axis or kind == "Crossings"
        uses_trajectory = (
            is_axis
            or is_projection
            or kind in {"Crossings", "Displacement", "Radius", "Return lags", "Returns", "Speed"}
        )
        self.axis_combo.setVisible(uses_axis)
        self.x_axis_combo.setVisible(is_projection)
        self.y_axis_combo.setVisible(is_projection)
        self.trajectory_spin.setVisible(uses_trajectory)
        self.separation_a_spin.setVisible(is_separation)
        self.separation_b_spin.setVisible(is_separation)
        self.log_check.setVisible(kind == "Separation")
        show_return_options = kind in {"Return lags", "Returns"}
        for widget in self.return_option_rows:
            self._set_options_row_visible(widget, show_return_options)
        show_crossing_options = kind == "Crossings"
        for widget in self.crossing_option_rows:
            self._set_options_row_visible(widget, show_crossing_options)
        show_fit_options = kind == "Separation fit"
        for widget in self.fit_option_rows:
            self._set_options_row_visible(widget, show_fit_options)
        self._sync_fit_option_enabled()

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

    def _emit_follow(self):
        display_kind = self.follow_kind_combo.currentText()
        kind = display_kind.lower().replace(" ", "_")
        options = {
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
                options["direction"] = self.crossing_direction_combo.currentText().lower()
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
            if kind in {"return_lags", "returns"}:
                options["samples"] = self.return_samples_spin.value()
                options["min_lag"] = self.return_min_lag_spin.value()
                options["count"] = self.return_count_spin.value()
                options["unique"] = self.return_unique_check.isChecked()
        self.follow_requested.emit(kind, options)
