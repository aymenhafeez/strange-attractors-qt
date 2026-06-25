from functools import partial

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .solver import solve_attractor
from .registry import ATTRACTORS


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = gl.GLViewWidget()
        container = QtWidgets.QWidget()
        container.setStyleSheet("border: 1px solid #555;")
        container_layout = QtWidgets.QGridLayout(container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(3)
        container_layout.addWidget(self.view, 0, 0)
        container_layout.setRowStretch(0, 1)
        container_layout.setColumnStretch(0, 1)

        self.equation_label = QtWidgets.QLabel("")
        self.equation_label.setStyleSheet("""
            color: #ddd;
            font-size: 13px;
            padding: 2px 6px;
            background: rgba(0, 0, 0, 0);
            border-radius: 0px;
            border-left: 0px;
            border-top: 0px;
        """)
        container_layout.addWidget(
            self.equation_label,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
        )

        status_container = QtWidgets.QWidget()
        status_container.setStyleSheet("background-color: #000000;")
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(0)

        self.status_system = QtWidgets.QLabel("")
        self.status_params = QtWidgets.QLabel("")
        self.status_ic = QtWidgets.QLabel("")
        for lbl in [self.status_system, self.status_params, self.status_ic]:
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            status_layout.addWidget(lbl, stretch=1)

        status_container.setFixedHeight(22)
        container_layout.addWidget(status_container, 1, 0)
        self.status_system.setStyleSheet("""
            color: #aaa;
            font-size: 12px;
            border-left: 0px;
        """)
        self.status_ic.setStyleSheet("""
            color: #aaa;
            font-size: 12px;
            border-right: 0px;
        """)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        splitter.addWidget(container)

        layout.addWidget(splitter)

        grid_xy = gl.GLGridItem()
        grid_xy.setSize(x=200, y=200, z=1)
        grid_xy.setSpacing(x=20, y=20, z=1)
        grid_xy.translate(dx=0, dy=0, dz=-100)
        self.view.addItem(grid_xy)

        grid_yz = gl.GLGridItem()
        grid_yz.setSize(x=200, y=200, z=1)
        grid_yz.setSpacing(x=20, y=20, z=1)
        grid_yz.rotate(90, 1, 0, 0)
        grid_yz.translate(0, -100, 0)
        self.view.addItem(grid_yz)

        grid_xz = gl.GLGridItem()
        grid_xz.setSize(x=200, y=200, z=1)
        grid_xz.setSpacing(x=20, y=20, z=1)
        grid_xz.rotate(90, 0, 1, 0)
        grid_xz.translate(-100, 0, 0)
        self.view.addItem(grid_xz)

        grid_yx = gl.GLGridItem()
        grid_yx.setSize(x=200, y=200, z=1)
        grid_yx.setSpacing(x=20, y=20, z=1)
        grid_yx.translate(dx=0, dy=0, dz=100)
        self.view.addItem(grid_yx)

        grid_zy = gl.GLGridItem()
        grid_zy.setSize(x=200, y=200, z=1)
        grid_zy.setSpacing(x=20, y=20, z=1)
        grid_zy.rotate(90, 1, 0, 0)
        grid_zy.translate(dx=0, dy=100, dz=0)
        self.view.addItem(grid_zy)

        grid_zx = gl.GLGridItem()
        grid_zx.setSize(x=200, y=200, z=1)
        grid_zx.setSpacing(x=20, y=20, z=1)
        grid_zx.rotate(90, 0, 1, 0)
        grid_zx.translate(dx=100, dy=0, dz=0)
        self.view.addItem(grid_zx)

        self.line = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)), color=(1, 1, 1, 1), size=1.0, pxMode=True
        )
        self.line.translate(dx=0, dy=0, dz=-15)
        self.view.addItem(self.line)

        self.panel = QtWidgets.QWidget()
        self.panel.setStyleSheet("""
            QWidget#controlPanel {
                background-color: #000000;
                border: 1px solid #555;
            }
            QSlider:horizontal {
                min-height: 30px;
                max-height: 30px;
            }
            QSlider::groove:horizontal {
                background: #555;
                border-radius: 0px;
            }
            QSlider::handle:horizontal {
                background: #aaa;
                width: 6px;
                min-height: 30px;
                max-height: 30px;
                margin: 0;
            }
        """)
        self.panel.setObjectName("controlPanel")
        self.panel_layout = QtWidgets.QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(15)

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        self.dropdown.setStyleSheet("""
            QPushButton {
                background-color: #000000;
                color: white;
                border: 1px solid #555;
                border-radius: 0px;
                padding: 4px 8px;
                text-align: left;
            }
        """)

        menu = QtWidgets.QMenu(self.dropdown)
        menu.setStyleSheet("""
            QMenu {
                background-color: #000000;
                border: 1px solid #555;
            }
            QMenu::item {
                background-color: #000000;
                color: white;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #dddddd;
                color: #000000;
            }
        """)

        for name in ATTRACTORS:
            action = menu.addAction(name)
            action.triggered.connect(partial(self.on_attractor_change, name))
        self.dropdown.setMenu(menu)
        self.panel_layout.addWidget(self.dropdown)

        splitter.addWidget(self.panel)
        splitter.setSizes([int(1100 * 0.7), int(1100 * 0.3)])

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet("color: #ddd; font-size: 12px")
        self.info_label.setWordWrap(True)

        self.projection_container = QtWidgets.QWidget()
        proj_layout = QtWidgets.QVBoxLayout(self.projection_container)
        proj_layout.setContentsMargins(0, 0, 0, 0)
        proj_layout.setSpacing(3)

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
            pw.getViewBox().setContentsMargins(0, 0, 0, 0)
            pw.getViewBox().setAspectLocked(True)
            img = pg.ImageItem()
            cmap = pg.colormap.get("CET-L1")
            img.setLookupTable(cmap.getLookupTable())
            pw.addItem(img)
            self.image_items[key] = (img, pw)
            pw.getPlotItem().addColorBar(
                img,
                values=(0, 10),
                colorMap=pg.colormap.get("CET-L1"),
                width=10,
            )
            proj_layout.addWidget(pw)

        self.rebuild_sliders(self.current_name)

        self.panel_layout.addWidget(self.info_label)

    def rebuild_sliders(self, name):
        self.panel_layout.removeWidget(self.info_label)
        self.panel_layout.removeWidget(self.projection_container)

        for _, _, row_layout in self.slider_rows:
            while row_layout.count():
                item = row_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
            self.panel_layout.removeItem(row_layout)
        self.slider_rows.clear()

        while self.panel_layout.count():
            item = self.panel_layout.itemAt(self.panel_layout.count() - 1)
            if item.spacerItem():
                self.panel_layout.takeAt(self.panel_layout.count() - 1)
            else:
                break

        config = ATTRACTORS[name]
        self.info_label.setText(config.description)
        self.info_label.setVisible(bool(config.description))
        self.equation_label.setText(config.equation_text)
        self.equation_label.setVisible(bool(config.equation_text))
        self.view.setCameraPosition(
            pos=QtGui.QVector3D(0, 0, 0),
            distance=config.camera_distance,
            elevation=config.camera_elevation,
            azimuth=config.camera_azimuth,
        )
        self.view.opts["center"] = QtGui.QVector3D(
            self.view.opts["center"].x(),
            self.view.opts["center"].y(),
            self.view.opts["center"].z() + config.pan,
        )

        for p in config.params:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(p.name)
            label.setStyleSheet("color: white; font-weight: bold;")
            row.addWidget(label)
            s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            s.setRange(int(p.min_val / p.step), int(p.max_val / p.step))
            s.setValue(int(p.default / p.step))
            s.setMinimumHeight(50)
            s.setMaximumHeight(50)
            val_label = QtWidgets.QLabel(f"{p.default:.2f}")
            val_label.setStyleSheet("color: white; font-weight: bold;")
            s.valueChanged.connect(
                lambda val, vlable=val_label, step=p.step: vlable.setText(
                    f"{val * step:.2f}"
                )
            )
            s.valueChanged.connect(self.update_plot)
            row.addWidget(s)
            row.addWidget(val_label)
            self.slider_rows.append((p, s, row))
            self.panel_layout.addLayout(row)

        self.panel_layout.addStretch()
        self.panel_layout.addWidget(self.projection_container)
        self.panel_layout.addWidget(self.info_label)
        self.update_plot()

    def on_attractor_change(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        self.rebuild_sliders(name)

    def update_plot(self):
        config = ATTRACTORS[self.current_name]
        values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}
        solution = solve_attractor(config, values)
        x, y, z = solution.T
        self.line.setData(pos=solution)

        projection_data = {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}

        bins_resolution = 64

        for key, (data_h, data_v) in projection_data.items():
            img, pw = self.image_items[key]

            heatmap, xedges, yedges = np.histogram2d(
                data_h, data_v, bins=bins_resolution
            )
            heatmap_log = np.log1p(heatmap)

            img.setImage(heatmap_log)

            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))

            pw.autoRange()

        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        self.status_system.setText(f"System: {config.name}")
        self.status_params.setText(f"Params: {formatted_params}")
        self.status_ic.setText(f"IC: {config.initial_conditions}")


if __name__ == "__main__":
    app = pg.mkQApp()
    app.setStyle("Fusion")
    w = Window()
    w.resize(1100, 800)
    w.show()
    pg.exec()
