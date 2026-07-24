import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .style import EQUATION_LABEL, LYAPUNOV_PLOT


class LyapunovOverlay:
    def __init__(self, parent_layout):
        self.label = QtWidgets.QLabel("")
        self.label.setStyleSheet(EQUATION_LABEL)

        self.plot = pg.PlotWidget()
        self.plot.setFixedSize(300, 150)
        self.plot.setBackground(None)
        self.plot.hideAxis("bottom")
        self.plot.hideAxis("left")
        self.plot.setStyleSheet(LYAPUNOV_PLOT)
        self.curve_l1 = self.plot.plot([], [], pen=(255, 100, 100))
        self.curve_l2 = self.plot.plot([], [], pen=(100, 255, 100))
        self.curve_l3 = self.plot.plot([], [], pen=(100, 100, 255))

        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet(LYAPUNOV_PLOT)
        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.plot, alignment=QtCore.Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.label, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        parent_layout.addWidget(
            self.container,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom,
        )
        self.container.setVisible(False)

    def set_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.label.setText(
            f"λ = ({lyap[0]:+.2f}, {lyap[1]:+.2f}, {lyap[2]:+.2f})  D_KY = {ky_dim:.2f}"
        )
        self.container.setVisible(True)
        self.curve_l1.setData(t_hist, lyap_hist[:, 0])
        self.curve_l2.setData(t_hist, lyap_hist[:, 1])
        self.curve_l3.setData(t_hist, lyap_hist[:, 2])

    def clear(self):
        self.label.setText("")
        self.container.setVisible(False)
