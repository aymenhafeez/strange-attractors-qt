from pyqtgraph.Qt import QtCore, QtWidgets

STATUS_BUTTON_WIDTH = 58


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
        self.follow_kind_combo.addItems(["Axis", "Projection", "Separation"])
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
        self.options_button = QtWidgets.QToolButton()
        self.options_button.setText("Options")
        self.options_button.setToolTip("Follow options")
        self.options_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.options_button.setMenu(self._build_options_menu())
        self.follow_button = QtWidgets.QPushButton("Follow")
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
        widget = QtWidgets.QWidget(menu)
        layout = QtWidgets.QFormLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addRow(self.append_check)
        layout.addRow("Label", self.label_edit)

        action = QtWidgets.QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)
        return menu

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
        is_separation = kind == "Separation"
        self.axis_combo.setVisible(is_axis)
        self.x_axis_combo.setVisible(is_projection)
        self.y_axis_combo.setVisible(is_projection)
        self.trajectory_spin.setVisible(is_axis or is_projection)
        self.separation_a_spin.setVisible(is_separation)
        self.separation_b_spin.setVisible(is_separation)
        self.log_check.setVisible(is_separation)

    def _emit_follow(self):
        kind = self.follow_kind_combo.currentText().lower()
        options = {
            "append": self.append_check.isChecked(),
            "label": self.label_edit.text().strip() or None,
        }
        if kind == "axis":
            options["axis"] = self.axis_combo.currentText()
            options["trajectory"] = self.trajectory_spin.value()
        elif kind == "projection":
            options["x_axis"] = self.x_axis_combo.currentText()
            options["y_axis"] = self.y_axis_combo.currentText()
            options["trajectory"] = self.trajectory_spin.value()
        else:
            options["a"] = self.separation_a_spin.value()
            options["b"] = self.separation_b_spin.value()
            options["log"] = self.log_check.isChecked()
        self.follow_requested.emit(kind, options)
