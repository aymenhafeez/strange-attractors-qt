import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.style import equation_label, plot_colours


class ViewportOverlay:
    def __init__(self, container, layout, view):
        self.container = container
        self.view = view
        self.equation_label = QtWidgets.QLabel("")
        self.equation_label.setStyleSheet(equation_label())
        layout.addWidget(
            self.equation_label,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom,
        )

        self.colourbar = ColourBarWidget(container)
        self.colourbar.setStyleSheet(f"color: {plot_colours()['colourbar_text']};")
        layout.addWidget(
            self.colourbar,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom,
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

    def apply_theme(self):
        self.equation_label.setStyleSheet(equation_label())
        self.colourbar.setStyleSheet(f"color: {plot_colours()['colourbar_text']};")


class ColourBarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "solid"
        self._cmap = "viridis"
        self._limits = None

        self.setFixedSize(90, 240)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def set_scale(self, mode, cmap, limits):
        self._mode = mode
        self._cmap = cmap
        self._limits = limits

        self.setVisible(mode != "solid" and limits is not None)
        self.update()

    def paintEvent(self, a0):
        if self._limits is None:
            return

        vmin, vmax = self._limits
        cmap = pg.colormap.get(self._cmap, source="matplotlib")

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        bar = QtCore.QRectF(8, 28, 18, self.height() - 56)

        painter.fillRect(
            bar, cmap.getBrush((bar.bottom(), bar.top()), orientation="vertical")
        )
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.WindowText))
        painter.drawRect(bar)

        title = {"speed": "Speed", "x": "X", "y": "Y", "z": "Z"}.get(
            self._mode, self._mode
        )
        painter.drawText(4, 16, title)
        painter.drawText(32, 36, f"{vmax:.4g}")
        painter.drawText(32, self.height() - 20, f"{vmin:.4g}")
