"""Render a selected 2D projection as a binned density heatmap. LineSegmentROI samples the displayed
density field and shows the 1D density profile along the selected intersection

Adapted from the PyQtGraph data slicing example
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .style import plot_colours

PROJECTIONS = {
    "XY": (0, 1, ("X", "Y")),
    "XZ": (0, 2, ("X", "Z")),
    "YZ": (1, 2, ("Y", "Z")),
}


class ProjectionPanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._projection_data = None
        self._points = None
        self._projection_key = "XY"
        self._heatmap = None
        self._image_data = None
        self._roi_placed = False
        self.setMinimumHeight(220)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        controls_layout.addWidget(QtWidgets.QLabel("Projection:"))
        self.projection_combo = QtWidgets.QComboBox()
        self.projection_combo.addItems(list(PROJECTIONS))
        self.projection_combo.currentTextChanged.connect(self._on_projection_changed)
        controls_layout.addWidget(self.projection_combo)

        controls_layout.addStretch(3)
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        controls_layout.addWidget(spacer)

        controls_layout.addWidget(QtWidgets.QLabel("Map:"))
        self.dropdown = QtWidgets.QComboBox()
        colourmaps = pg.colormap.listMaps()
        self.dropdown.addItems(colourmaps)
        self.dropdown.setCurrentText(plot_colours()["cmap"])
        self.dropdown.currentTextChanged.connect(self._update_colourmap)
        self.dropdown.setMaxVisibleItems(12)
        # needed for setMaxVisibleItems to apply
        self.dropdown.setStyleSheet("QComboBox { combobox-popup: 0; }")
        controls_layout.addWidget(self.dropdown, 1)
        layout.addLayout(controls_layout)

        split_layout = QtWidgets.QHBoxLayout()
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(4)
        layout.addLayout(split_layout, 1)

        plot_layout = QtWidgets.QVBoxLayout()
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)
        split_layout.addLayout(plot_layout, 1)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(plot_colours()["plot_background"])
        self.plot_widget.showGrid(
            x=True, y=True, alpha=plot_colours()["plot_grid_alpha"]
        )
        # self.plot_widget.getPlotItem().setContentsMargins(0, 10, 0, 0)
        self.plot_widget.getViewBox().setAspectLocked(True)
        plot_layout.addWidget(self.plot_widget, 2)

        self.img = pg.ImageItem()
        self.plot_widget.addItem(self.img)
        self.image_items = {key: (self.img, self.plot_widget) for key in PROJECTIONS}

        self.roi_line = pg.LineSegmentROI(
            [[0.0, 0.0], [1.0, 0.0]],
            pen=pg.mkPen("r", width=3),
            hoverPen=pg.mkPen("y", width=4),
        )
        self.roi_line.sigRegionChanged.connect(self._update_profile)
        self.roi_line.setVisible(False)
        self.plot_widget.addItem(self.roi_line)

        self.profile_plot = pg.PlotWidget()
        self.profile_plot.setBackground(plot_colours()["plot_background"])
        self.profile_plot.showGrid(
            x=True, y=True, alpha=plot_colours()["plot_grid_alpha"]
        )
        self.profile_plot.setLabel("bottom", "Distance")
        self.profile_plot.setLabel("left", "Density")
        # self.profile_plot.getPlotItem().setContentsMargins(0, 10, 0, 0)
        self.profile_curve = self.profile_plot.plot([], [])
        plot_layout.addWidget(self.profile_plot, 1)

        self.histogram = pg.HistogramLUTWidget()
        self.histogram.setBackground(plot_colours()["plot_background"])
        self.histogram.item.setImageItem(self.img)
        self.histogram.item.gradient.setColorMap(
            pg.colormap.get(self.dropdown.currentText())
        )
        split_layout.addWidget(self.histogram)

        self.profile_label = QtWidgets.QLabel("")
        self.profile_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.profile_label)

        self.clear()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._render_cached_projection_data)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_cached_projection_data()

    def update_projections(self, x, y, z):
        self._projection_data = (x, y, z)
        points = np.column_stack((x, y, z))
        self._points = points[np.isfinite(points).all(axis=1)]
        self._render_projection_data(reset_roi=not self._roi_placed)

    def reapply_projections(self, solutions):
        if solutions:
            all_sol = np.concatenate(solutions, axis=0)
            x, y, z = all_sol.T
            self.update_projections(x, y, z)

    def clear(self):
        self._points = None
        self._heatmap = None
        self._image_data = None
        self._roi_placed = False
        self.img.clear()
        self.img.setVisible(False)
        self.roi_line.setVisible(False)
        self.histogram.setVisible(False)
        self.profile_curve.setData([], [], pen=plot_colours()["scatter_brush"])
        self.profile_label.setText("")

    def _render_cached_projection_data(self):
        if self._projection_data is not None:
            self._render_projection_data(reset_roi=False)

    def _on_projection_changed(self, key):
        self._projection_key = key
        self._roi_placed = False
        self._render_cached_projection_data()

    def _render_projection_data(self, *, reset_roi=False):
        if self._points is None or len(self._points) == 0:
            self.clear()
            return

        h_col, v_col, (lh, lv) = PROJECTIONS[self._projection_key]
        h = self._points[:, h_col]
        v = self._points[:, v_col]
        self._heatmap, xedges, yedges = np.histogram2d(h, v, bins=128)
        self._image_data = np.log1p(self._heatmap)

        self.img.setImage(self._image_data)
        self.img.setVisible(True)
        x_min, x_max = xedges[0], xedges[-1]
        y_min, y_max = yedges[0], yedges[-1]
        self.img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
        self.plot_widget.setLabel("bottom", lh)
        self.plot_widget.setLabel("left", lv)
        self._set_histogram_levels(self._image_data)
        self.histogram.setVisible(True)

        if reset_roi or not self._roi_placed:
            self._place_default_roi(xedges, yedges)

        self.roi_line.setVisible(True)
        self._update_profile()
        self.plot_widget.autoRange()

    def _set_histogram_levels(self, image_data):
        occupied = image_data[np.isfinite(image_data) & (image_data > 0)]
        if len(occupied) == 0:
            occupied = image_data[np.isfinite(image_data)]
        if len(occupied) == 0:
            return

        minimum = float(np.percentile(occupied, 5))
        maximum = float(np.percentile(occupied, 99.5))
        if minimum == maximum:
            maximum = minimum + 1.0

        self.histogram.item.setLevels(minimum, maximum)
        self.histogram.item.setHistogramRange(minimum, maximum)

    def _place_default_roi(self, xedges, yedges):
        x_min, x_max = float(xedges[0]), float(xedges[-1])
        y_mid = float((yedges[0] + yedges[-1]) / 2)
        x_pad = (x_max - x_min) * 0.1
        state = self.roi_line.saveState()
        state["points"] = [(x_min + x_pad, y_mid), (x_max - x_pad, y_mid)]
        self.roi_line.blockSignals(True)
        self.roi_line.setState(state)
        self.roi_line.blockSignals(False)
        self._roi_placed = True

    def _update_profile(self):
        if self._image_data is None:
            return

        profile = self.roi_line.getArrayRegion(self._image_data, self.img)
        if profile is None:
            self.profile_curve.setData([], [])
            self.profile_label.setText("No profile")
            return

        profile = np.asarray(profile, dtype=np.float64).squeeze()
        if profile.ndim != 1 or len(profile) == 0:
            self.profile_curve.setData([], [])
            self.profile_label.setText("No profile")
            return

        distance = np.arange(len(profile), dtype=np.float64)
        self.profile_curve.setData(distance, profile)
        self.profile_plot.autoRange()
        self._update_profile_label(profile)

    def _update_profile_label(self, profile):
        total = float(np.nansum(np.expm1(profile)))
        peak = float(np.nanmax(profile))
        self.profile_label.setText(
            f"{self._projection_key} transect bins {len(profile)} | "
            f"sum {total:.0f} | peak log density {peak:.4g}"
        )

    def _update_colourmap(self, cmap_name):
        cmap = pg.colormap.get(cmap_name)
        self.img.setLookupTable(cmap.getLookupTable())
        self.histogram.item.gradient.setColorMap(cmap)
        self._render_cached_projection_data()

    def apply_theme(self):
        colours = plot_colours()
        self.dropdown.setCurrentText(colours["cmap"])
        self.plot_widget.setBackground(colours["plot_background"])
        self.plot_widget.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])
        self.profile_plot.setBackground(colours["plot_background"])
        self.profile_plot.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])
        self.profile_curve.setPen(pg.mkPen(colours["scatter_brush"]))
        self.histogram.setBackground(colours["plot_background"])
