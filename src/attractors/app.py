from functools import partial

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .solver import solve_attractor
from .registry import ATTRACTORS
from .style import (
    EQUATION_LABEL,
    STATUS_BAR,
    STATUS_SYSTEM,
    STATUS_PARAMS,
    STATUS_IC,
    SLIDERS,
    DROPDOWN_BOX,
    DROPDOWN_SELECTION,
    ATTRACTOR_INFO,
    SLIDER_PARAMS,
    SLIDER_VALS,
)

WINDOW_SIZE = 1100
N_BINS = 96


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Strange Attractors")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.anim_frame = 0
        self.anim_step = 250
        self.full_solution = None
        self.timer = QtCore.QTimer()
        self.anim_button = QtWidgets.QPushButton("Play")
        self.timer.timeout.connect(self.animate_frame)

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
        self.equation_label.setStyleSheet(EQUATION_LABEL)
        container_layout.addWidget(
            self.equation_label,
            0,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
        )

        status_container = QtWidgets.QWidget()
        status_container.setStyleSheet(STATUS_BAR)
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(0)

        self.status_system = QtWidgets.QLabel("")
        self.status_params = QtWidgets.QLabel("")
        self.status_ic = QtWidgets.QLabel("")
        for lbl in [self.status_system, self.status_params, self.status_ic]:
            lbl.setStyleSheet(STATUS_PARAMS)
            status_layout.addWidget(lbl, stretch=1)

        status_container.setFixedHeight(22)
        container_layout.addWidget(status_container, 1, 0)
        self.status_system.setStyleSheet(STATUS_SYSTEM)
        self.status_ic.setStyleSheet(STATUS_IC)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        splitter.addWidget(container)

        layout.addWidget(splitter)

        grid_faces = [
            ("XY", [], (0, 0, -100)),
            ("YZ", [(90, 1, 0, 0)], (0, -100, 0)),
            ("XZ", [(90, 0, 1, 0)], (-100, 0, 0)),
            ("YX", [], (0, 0, 100)),
            ("ZY", [(90, 1, 0, 0)], (0, 100, 0)),
            ("ZX", [(90, 0, 1, 0)], (100, 0, 0)),
        ]

        for _, rotations, (dx, dy, dz) in grid_faces:
            g = gl.GLGridItem()
            g.setSize(x=200, y=200, z=1)
            g.setSpacing(x=20, y=20, z=1)
            for angle, *axis in rotations:
                g.rotate(angle, *axis)
            g.translate(dx, dy, dz)
            self.view.addItem(g)

        # self.line = gl.GLScatterPlotItem(
        self.line = gl.GLScatterPlotItem(
            pos=np.zeros((1, 3)), color=(1, 1, 1, 1), size=1.5, pxMode=True
        )
        self.view.addItem(self.line)

        self.panel = QtWidgets.QWidget()
        self.panel.setStyleSheet(SLIDERS)
        self.panel.setObjectName("controlPanel")
        self.panel_layout = QtWidgets.QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(15)

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        self.dropdown.setStyleSheet(DROPDOWN_BOX)

        menu = QtWidgets.QMenu(self.dropdown)
        menu.setStyleSheet(DROPDOWN_SELECTION)

        for name in ATTRACTORS:
            action = menu.addAction(name)
            action.triggered.connect(partial(self.on_attractor_change, name))
        self.dropdown.setMenu(menu)
        self.panel_layout.addWidget(self.dropdown)

        self.anim_button.clicked.connect(self.toggle_animation)
        self.panel_layout.addWidget(self.anim_button)

        splitter.addWidget(self.panel)
        splitter.setSizes([int(WINDOW_SIZE * 0.7), int(WINDOW_SIZE * 0.3)])

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setStyleSheet(ATTRACTOR_INFO)
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

        self.rebuild_view(self.current_name)

        self.panel_layout.addWidget(self.info_label)

    def toggle_animation(self):
        if self.timer.isActive():
            self.timer.stop()
            self.anim_button.setText("Play")
        else:
            self.anim_frame = 0
            self.timer.start(16)
            self.anim_button.setText("Pause")

    def animate_frame(self):
        sol = self.full_solution
        if sol is None:
            return

        frame = min(self.anim_frame + self.anim_step, len(sol))
        self.anim_frame = frame
        partial = sol[:frame]
        x, y, z = partial.T
        self.line.setData(pos=partial)
        self.update_projections(x, y, z)

        if frame >= len(sol):
            self.timer.stop()
            self.anim_button.setText("Play")

    def rebuild_view(self, name):
        self.timer.stop()
        self.anim_button.setText("Play")

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
            label.setStyleSheet(SLIDER_PARAMS)
            row.addWidget(label)
            s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            s.setRange(int(p.min_val / p.step), int(p.max_val / p.step))
            s.setValue(int(p.default / p.step))
            s.setMinimumHeight(50)
            s.setMaximumHeight(50)
            val_label = QtWidgets.QLabel(f"{p.default:.2f}")
            val_label.setStyleSheet(SLIDER_VALS)
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
        self.rebuild_view(name)

    def update_plot(self):
        self.timer.stop()
        self.anim_button.setText("Play")

        config = ATTRACTORS[self.current_name]
        values = {p.name: p.step * s.value() for p, s, _ in self.slider_rows}
        self.full_solution = solve_attractor(config, values)
        x, y, z = self.full_solution.T
        self.line.setData(pos=self.full_solution)

        self.update_projections(x, y, z)

        formatted_params = "  ".join(f"{k}: {v:.2f}" for k, v in sorted(values.items()))
        self.status_system.setText(f"System: {config.name}")
        self.status_params.setText(f"Params: {formatted_params}")
        self.status_ic.setText(f"IC: {config.initial_conditions}")

    def update_projections(self, x, y, z):
        for key, (data_h, data_v) in {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}.items():
            img, pw = self.image_items[key]
            heatmap, xedges, yedges = np.histogram2d(data_h, data_v, bins=N_BINS)
            img.setImage(np.log1p(heatmap))

            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            pw.autoRange()
