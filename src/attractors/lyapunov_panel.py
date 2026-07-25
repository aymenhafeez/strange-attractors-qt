import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets


class LyapunovPanel(QtWidgets.QWidget):
    compute_requested = QtCore.pyqtSignal()
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(QtWidgets.QLabel("Lyapunov"))

        self.auto_check = QtWidgets.QCheckBox("Auto")
        self.auto_check.setChecked(True)
        header.addWidget(self.auto_check)

        self.compute_button = QtWidgets.QPushButton("Compute")
        self.compute_button.clicked.connect(self.compute_requested.emit)
        header.addWidget(self.compute_button)

        header.addStretch(1)

        self.close_button = QtWidgets.QToolButton()
        self.close_button.setText("×")
        self.close_button.setAutoRaise(True)
        self.close_button.setFixedSize(18, 18)
        self.close_button.clicked.connect(self.close_requested.emit)
        header.addWidget(self.close_button)

        layout.addLayout(header)

        self.result_label = QtWidgets.QLabel("No Lyapunov result")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("k")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "t")
        self.plot.setLabel("left", "λ")
        layout.addWidget(self.plot)

        self.curve_l1 = self.plot.plot([], [], pen=(255, 100, 100))
        self.curve_l2 = self.plot.plot([], [], pen=(100, 255, 100))
        self.curve_l3 = self.plot.plot([], [], pen=(100, 100, 255))

    def auto_enabled(self):
        return self.auto_check.isChecked()

    def set_auto_enabled(self, enabled):
        self.auto_check.setChecked(bool(enabled))

    def set_result(self, lyap, ky_dim, t_hist, lyap_hist):
        self.result_label.setText(
            f"λ = ({lyap[0]:+.2f}, {lyap[1]:+.2f}, {lyap[2]:+.2f})  D_KY = {ky_dim:.2f}"
        )
        self.curve_l1.setData(t_hist, lyap_hist[:, 0])
        self.curve_l2.setData(t_hist, lyap_hist[:, 1])
        self.curve_l3.setData(t_hist, lyap_hist[:, 2])

    def clear(self):
        self.result_label.setText("No Lyapunov result")
        self.curve_l1.setData([], [])
        self.curve_l2.setData([], [])
        self.curve_l3.setData([], [])
