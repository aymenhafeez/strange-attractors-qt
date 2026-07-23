import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

N_BINS = 96


class ProjectionPanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._projection_data = None
        self.setMinimumHeight(140)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(2)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        header.addStretch()
        self.close_btn = QtWidgets.QToolButton()
        self.close_btn.setText("×")
        self.close_btn.setAutoRaise(True)
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self.close_btn)
        layout.addLayout(header)

        plots_layout = QtWidgets.QHBoxLayout()
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(4)
        layout.addLayout(plots_layout)

        self.image_items = {}
        for key, (lh, lv) in [
            ("XY", ("X", "Y")),
            ("XZ", ("X", "Z")),
            ("YZ", ("Y", "Z")),
        ]:
            pw = pg.PlotWidget()
            pw.showAxis("bottom", False)
            pw.showAxis("left", False)
            pw.showAxis("top", False)
            pw.showAxis("right", False)
            pw.setLabel("bottom", lh)
            pw.setLabel("left", lv)
            pw.getPlotItem().setContentsMargins(0, 10, 0, 0)
            pw.getViewBox().setAspectLocked(True)
            img = pg.ImageItem()
            cmap = pg.colormap.get("CMRmap", source="matplotlib")
            img.setLookupTable(cmap.getLookupTable())
            pw.addItem(img)
            self.image_items[key] = (img, pw)
            pw.getPlotItem().addColorBar(
                img,
                values=(0, 10),
                colorMap=cmap,
                width=10,
            )
            plots_layout.addWidget(pw)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._render_cached_projection_data)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_cached_projection_data()

    def update_projections(self, x, y, z):
        self._projection_data = (x, y, z)
        self._render_projection_data(x, y, z)

    def _render_cached_projection_data(self):
        if self._projection_data is not None:
            self._render_projection_data(*self._projection_data)

    def _render_projection_data(self, x, y, z):
        for key, (data_h, data_v) in {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}.items():
            img, pw = self.image_items[key]
            heatmap, xedges, yedges = np.histogram2d(
                data_h, data_v, bins=N_BINS, density=True
            )
            img.setImage(np.log1p(heatmap))
            img.setVisible(True)
            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            pw.autoRange()

    def reapply_projections(self, solutions):
        if solutions:
            all_sol = np.concatenate(solutions, axis=0)
            x, y, z = all_sol.T
            self.update_projections(x, y, z)
