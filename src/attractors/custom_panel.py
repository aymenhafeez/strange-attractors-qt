from attractors.style import SLIDER_PARAMS
from pyqtgraph.Qt import QtCore, QtWidgets

from .expression_parser import (
    ParseError,
    compile_system,
    format_equations,
)
from .models import AttractorConfig, AttractorParam
from .style import CUSTOM_PANEL, CUSTOM_TOGGLE, NO_BORDER

STEP = 0.01
DEFAULT_RANGE = (0.0, 50.0)


class CustomPanel(QtWidgets.QWidget):
    compile_requested = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.toggle_btn = QtWidgets.QPushButton("▼ Custom")
        self.toggle_btn.setStyleSheet(CUSTOM_TOGGLE)
        self.toggle_btn.clicked.connect(self._toggle_content)
        layout.addWidget(self.toggle_btn)

        self._content = QtWidgets.QWidget()
        self._content.setObjectName("customPanelContent")
        self._content.setStyleSheet(CUSTOM_PANEL)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(6, 6, 6, 4)
        content_layout.setSpacing(4)

        eq_label = QtWidgets.QLabel("Equations")
        eq_label.setStyleSheet(SLIDER_PARAMS)
        content_layout.addWidget(eq_label)

        self.text_edits: list[QtWidgets.QTextEdit] = []
        labels = ["dx/dt =", "dy/dt =", "dz/dt ="]
        placeholders = [
            "a * (y - x)",
            "x * (b - z) - y",
            "x * y - c * z",
        ]

        for label_text, placeholder in zip(labels, placeholders):
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(label_text)
            lbl.setStyleSheet(NO_BORDER)
            row.addWidget(lbl)

            te = QtWidgets.QTextEdit()
            te.setPlaceholderText(placeholder)
            te.setFixedHeight(32)
            te.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            te.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            row.addWidget(te)
            self.text_edits.append(te)
            content_layout.addLayout(row)

        ic_label = QtWidgets.QLabel("Initial Conditions")
        ic_label.setStyleSheet(SLIDER_PARAMS)
        content_layout.addWidget(ic_label)

        ic_row = QtWidgets.QHBoxLayout()
        self.ic_spins: list[QtWidgets.QDoubleSpinBox] = []
        for axis, default in [("x₀", 0.1), ("y₀", 0.0), ("z₀", 0.0)]:
            lbl = QtWidgets.QLabel(axis)
            lbl.setStyleSheet(SLIDER_PARAMS)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
            spin.setValue(default)
            ic_row.addWidget(lbl)
            ic_row.addWidget(spin)
            self.ic_spins.append(spin)
        content_layout.addLayout(ic_row)

        self.range_group = QtWidgets.QGroupBox()
        self.range_group.setStyleSheet(NO_BORDER)
        self.range_layout = QtWidgets.QVBoxLayout(self.range_group)
        self.range_layout.setContentsMargins(0, 4, 0, 0)
        self.range_group.hide()
        content_layout.addWidget(self.range_group)

        self._range_widgets: dict = {}

        self.compile_btn = QtWidgets.QPushButton("Compile")
        self.compile_btn.clicked.connect(self._on_compile)
        content_layout.addWidget(self.compile_btn)

        self.solve_btn = QtWidgets.QPushButton("Solve")
        self.solve_btn.clicked.connect(self._on_solve)
        self.solve_btn.hide()
        content_layout.addWidget(self.solve_btn)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        content_layout.addWidget(self.status_label)

        layout.addWidget(self._content)

    def _toggle_content(self):
        visible = not self._content.isVisible()
        self._content.setVisible(visible)
        self.toggle_btn.setText("▼ Custom" if visible else "▶ Custom")
        self.adjustSize()

    def _get_equations(self) -> tuple[str, str, str]:
        return tuple(te.toPlainText().strip() for te in self.text_edits)

    def _on_compile(self):
        equations = self._get_equations()

        if not all(equations):
            self._show_status("All three equations are required.", error=True)
            return

        try:
            func, detected_params = compile_system(equations)
        except ParseError as exc:
            self._show_status(f"Syntax error: {exc}", error=True)
            return
        except Exception as exc:
            self._show_status(f"Compilation failed: {exc}", error=True)
            return

        self.range_group.hide()
        self.solve_btn.hide()
        self.compile_btn.show()

        self._func = func
        self._detected_params = detected_params
        self._equation_text = format_equations(equations)

        if not detected_params:
            self._emit_config()
            return

        self._build_range_editors(detected_params)
        self.range_group.show()
        self.compile_btn.hide()
        self.solve_btn.show()
        self.adjustSize()

        self._show_status(
            f"Compiled — {len(detected_params)} parameter(s): "
            + ", ".join(detected_params)
            + ". Set ranges and click solve",
            error=False,
        )

    def _build_range_editors(self, params: list[str]):
        self._clear_layout(self.range_layout)
        self._range_widgets = {}

        header = QtWidgets.QHBoxLayout()
        for text in ("Min", "Max", "Step"):
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet("font-weight: bold;")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            header.addWidget(lbl)
        self.range_layout.addLayout(header)

        for p in params:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(p))

            mn = QtWidgets.QDoubleSpinBox()
            mn.setRange(-1e6, 1e6)
            mn.setDecimals(4)
            mn.setValue(DEFAULT_RANGE[0])
            row.addWidget(mn)

            mx = QtWidgets.QDoubleSpinBox()
            mx.setRange(-1e6, 1e6)
            mx.setDecimals(4)
            mx.setValue(DEFAULT_RANGE[1])
            row.addWidget(mx)

            st = QtWidgets.QDoubleSpinBox()
            st.setRange(1e-6, 1e6)
            st.setDecimals(6)
            st.setValue(STEP)
            row.addWidget(st)

            self.range_layout.addLayout(row)
            self._range_widgets[p] = [mn, mx, st]

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            r_layout = item.layout()
            if r_layout:
                self._clear_layout(r_layout)

    def _on_solve(self):
        self.range_group.hide()
        self.solve_btn.hide()
        self.compile_btn.show()
        self.adjustSize()
        self._emit_config()

    def _emit_config(self):
        params = []
        for p in self._detected_params:
            if p in self._range_widgets:
                mn, mx, st = self._range_widgets[p]
                params.append(
                    AttractorParam(p, 1.0, mn.value(), mx.value(), st.value())
                )
            else:
                params.append(AttractorParam(p, 1.0, *DEFAULT_RANGE, STEP))

        config = AttractorConfig(
            name="Custom",
            equation=self._func,
            params=params,
            initial_conditions=[spin.value() for spin in self.ic_spins],
            time_defaults={
                "t_min": 0,
                "t_max": 50,
                "n": 100000,
            },
            equation_text=self._equation_text,
            description="User-defined custom attractor",
        )

        self._show_status(
            f"Compiled — {len(params)} parameter(s): "
            + ", ".join(p.name for p in params),
            error=False,
        )

        self._detected_params = []
        self._func = None
        self._equation_text = ""
        self._range_widgets = {}

        self.compile_requested.emit(config)

    def _show_status(self, message: str, error: bool = False):
        self.status_label.setText(message)
        color = "#ff6b6b" if error else "#a8e6a3"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.show()
