from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.style import EQUATION_LABEL


class ViewportOverlay:
    def __init__(self, container, layout, view):
        self.container = container
        self.view = view
        self.equation_label = QtWidgets.QLabel("")
        self.equation_label.setStyleSheet(EQUATION_LABEL)
        layout.addWidget(
            self.equation_label,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom,
        )

    def set_info(self, config, values):
        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        equations = config.equation_text.replace("\n", "<br>")
        text = (
            f"<b>SYSTEM</b>: {config.name}<br>"
            f"{equations}<br>"
            f"<b>IC</b>: {config.initial_conditions}<br>"
            f"<b>PARAMS</b>: {formatted_params}"
        )
        self.equation_label.setText(text)
        self.equation_label.setVisible(True)
        self.equation_label.setToolTip(config.description)

    def save_view_as_png(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.container, "Save View as PNG", "", "PNG Files (*.png)"
        )
        if not filename:
            return False

        img = self.view.grabFramebuffer()

        return img.save(filename)
