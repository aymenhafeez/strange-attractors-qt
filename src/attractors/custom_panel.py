from PyQt6 import QtCore, QtWidgets

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
        self._content.setStyleSheet(CUSTOM_PANEL)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(6, 6, 6, 4)
        content_layout.setSpacing(4)

        eq_label = QtWidgets.QLabel("Equations")
        eq_label.setStyleSheet(NO_BORDER)
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
        ic_label.setStyleSheet(NO_BORDER)
        content_layout.addWidget(ic_label)

        ic_row = QtWidgets.QHBoxLayout()
        self.ic_spins: list[QtWidgets.QDoubleSpinBox] = []
        for axis, default in [("x₀", 0.1), ("y₀", 0.0), ("z₀", 0.0)]:
            lbl = QtWidgets.QLabel(axis)
            lbl.setStyleSheet(NO_BORDER)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
            spin.setValue(default)
            ic_row.addWidget(lbl)
            ic_row.addWidget(spin)
            self.ic_spins.append(spin)
        content_layout.addLayout(ic_row)

        self.compile_btn = QtWidgets.QPushButton("Compile and Solve")
        self.compile_btn.clicked.connect(self._on_compile)
        content_layout.addWidget(self.compile_btn)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        content_layout.addWidget(self.status_label)

        layout.addWidget(self._content)

    def _toggle_content(self):
        visible = not self._content.isVisible()
        self._content.setVisible(visible)
        self.toggle_btn.setText("▼ Custom" if visible else "▶ Custom")

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

        config = AttractorConfig(
            name="Custom",
            equation=func,
            params=[
                AttractorParam(p, 1.0, *DEFAULT_RANGE, STEP) for p in detected_params
            ],
            initial_conditions=[spin.value() for spin in self.ic_spins],
            time_defaults={
                "t_min": 0,
                "t_max": 50,
                "n": 100000,
            },
            equation_text=format_equations(equations),
            description="User-defined custom attractor",
        )

        self._show_status(
            f"Compiled — {len(detected_params)} parameter(s): "
            + ", ".join(detected_params),
            error=False,
        )

        self.compile_requested.emit(config)

    def _show_status(self, message: str, error: bool = False):
        self.status_label.setText(message)
        self.status_label.show()
