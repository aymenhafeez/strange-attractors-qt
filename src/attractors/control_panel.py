from functools import partial

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .registry import ATTRACTORS
from .style import (
    DROPDOWN_BOX,
    DROPDOWN_SELECTION,
    LINE_MODE_CHECKBOX,
    SLIDER_PARAMS,
    SLIDERS,
)

STEP = 1000
N_BINS = 96


class ControlPanel(QtWidgets.QWidget):
    attractor_changed = QtCore.pyqtSignal(str)
    solve_requested = QtCore.pyqtSignal(bool)
    bifurcation_requested = QtCore.pyqtSignal()
    poincare_requested = QtCore.pyqtSignal()
    n_changed = QtCore.pyqtSignal(int)
    t_max_changed = QtCore.pyqtSignal(int)
    animation_toggled = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlPanel")

        # plain QWidget to work around objectName selector bug on QWidget subclasses
        inner = QtWidgets.QWidget()
        inner.setObjectName("controlPanel")
        inner.setStyleSheet(SLIDERS)

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(inner)

        self.panel_layout = QtWidgets.QVBoxLayout(inner)
        self.panel_layout.setContentsMargins(8, 8, 8, 8)
        self.panel_layout.setSpacing(7)

        self.current_name = list(ATTRACTORS.keys())[0]
        self.slider_rows = []
        self.n_slider_row = None
        self.n_slider_wrapper = None
        self.t_max_slider_row = None
        self.t_max_slider_wrapper = None

        options = QtWidgets.QHBoxLayout()

        self.dropdown = QtWidgets.QPushButton(list(ATTRACTORS.keys())[0])
        self.dropdown.setStyleSheet(DROPDOWN_BOX)
        menu = QtWidgets.QMenu(self.dropdown)
        menu.setStyleSheet(DROPDOWN_SELECTION)
        for name in ATTRACTORS:
            action = menu.addAction(name)
            assert action is not None
            action.triggered.connect(partial(self._on_attractor_selected, name))
        custom_action = menu.addAction("Custom")
        assert custom_action is not None
        custom_action.triggered.connect(partial(self._on_attractor_selected, "Custom"))
        self.dropdown.setMenu(menu)

        self.tools_button = QtWidgets.QPushButton("Tools")
        self.tools_button.setStyleSheet(DROPDOWN_BOX)
        tools_menu = QtWidgets.QMenu(self.tools_button)
        tools_menu.setStyleSheet(DROPDOWN_SELECTION)
        bifurcation_action = tools_menu.addAction("Bifurcation diagram")
        bifurcation_action.triggered.connect(self.bifurcation_requested)
        poincare_action = tools_menu.addAction("Poincar\u00e9 section")
        poincare_action.triggered.connect(self.poincare_requested)
        self.tools_button.setMenu(tools_menu)

        options.addWidget(self.dropdown)
        options.addWidget(self.tools_button)
        self.panel_layout.addLayout(options)

        options_row = QtWidgets.QHBoxLayout()

        self.anim_button = QtWidgets.QPushButton("\u25b6 Play")
        self.anim_button.clicked.connect(self.animation_toggled)
        options_row.addWidget(self.anim_button)
        options_row.addStretch(1)

        self.line_mode = QtWidgets.QCheckBox("Line")
        self.line_mode.setChecked(False)
        self.line_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        options_row.addWidget(self.line_mode)

        self.trail_mode = QtWidgets.QCheckBox("Trail")
        self.trail_mode.setChecked(False)
        self.trail_mode.setStyleSheet(LINE_MODE_CHECKBOX)
        options_row.addWidget(self.trail_mode)

        self.show_grid = QtWidgets.QCheckBox("Grid")
        self.show_grid.setChecked(True)
        self.show_grid.setStyleSheet(LINE_MODE_CHECKBOX)
        options_row.addWidget(self.show_grid)

        self.panel_layout.addLayout(options_row)

        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.setSpacing(10)
        alpha_label = QtWidgets.QLabel("\u03b1 ")
        alpha_label.setStyleSheet(SLIDER_PARAMS)
        self.alpha_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(100)
        self.alpha_spin = QtWidgets.QSpinBox()
        self.alpha_spin.setKeyboardTracking(False)
        self.alpha_spin.setRange(0, 100)
        self.alpha_spin.setValue(100)
        self.alpha_slider.valueChanged.connect(self.alpha_spin.setValue)
        self.alpha_spin.valueChanged.connect(self.alpha_slider.setValue)
        alpha_row.addWidget(alpha_label)
        alpha_row.addWidget(self.alpha_slider)
        alpha_row.addWidget(self.alpha_spin)
        alpha_wrapper = QtWidgets.QWidget()
        alpha_wrapper.setLayout(alpha_row)
        self.panel_layout.addWidget(alpha_wrapper)

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
            pw.getPlotItem().setContentsMargins(0, 10, 0, 0)
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

    def _on_attractor_selected(self, name):
        self.current_name = name
        self.dropdown.setText(name)
        self.attractor_changed.emit(name)

    def set_anim_playing(self, playing):
        self.anim_button.setText("\u25a0 Stop" if playing else "\u25b6 Play")

    def configure(self, config):
        self._clear_sliders()
        self._build_n_slider(config)
        self._build_t_max_slider(config)
        self._build_param_sliders(config)
        self.panel_layout.addStretch()
        self.panel_layout.addWidget(self.projection_container)

    def _clear_sliders(self):
        if self.n_slider_wrapper is not None:
            self.panel_layout.removeWidget(self.n_slider_wrapper)
            self.n_slider_wrapper.deleteLater()
            self.n_slider_row = None
            self.n_slider_wrapper = None
        if self.t_max_slider_wrapper is not None:
            self.panel_layout.removeWidget(self.t_max_slider_wrapper)
            self.t_max_slider_wrapper.deleteLater()
            self.t_max_slider_row = None
            self.t_max_slider_wrapper = None
        for *_, wrapper in self.slider_rows:
            self.panel_layout.removeWidget(wrapper)
            wrapper.deleteLater()
        self.slider_rows.clear()
        while self.panel_layout.count():
            item = self.panel_layout.itemAt(self.panel_layout.count() - 1)
            if item.widget() is self.projection_container:
                self.panel_layout.removeWidget(self.projection_container)
                break
            if item is not None and item.spacerItem():
                self.panel_layout.takeAt(self.panel_layout.count() - 1)
            else:
                break

    def _build_n_slider(self, config):
        n_row = QtWidgets.QHBoxLayout()
        self.n_slider_row = n_row
        n_label = QtWidgets.QLabel("N")
        n_label.setStyleSheet("color: white;")
        n_row.addWidget(n_label)
        n_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        n_slider.setRange(1, 500)
        n_slider.setValue(int(config.time_defaults["n"] / STEP))
        n_slider.param_step = STEP
        n_spin = QtWidgets.QSpinBox()
        n_spin.setKeyboardTracking(False)
        n_spin.setRange(1000, 500000)
        n_spin.setSingleStep(STEP)
        n_spin.setValue(config.time_defaults["n"])
        n_spin.param_step = STEP
        n_slider.valueChanged.connect(
            lambda val: n_spin.setValue(val * n_slider.param_step)
        )
        n_slider.valueChanged.connect(lambda: self.solve_requested.emit(False))
        n_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        n_spin.valueChanged.connect(
            lambda val: n_slider.setValue(int(val / n_spin.param_step))
        )
        n_spin.valueChanged.connect(self.n_changed.emit)
        n_row.addWidget(n_slider)
        n_row.addWidget(n_spin)
        self.n_slider_wrapper = QtWidgets.QWidget()
        self.n_slider_wrapper.setLayout(n_row)
        self.panel_layout.addWidget(self.n_slider_wrapper)

    def _build_t_max_slider(self, config):
        t_max_row = QtWidgets.QHBoxLayout()
        self.t_max_slider_row = t_max_row
        t_max_label = QtWidgets.QLabel("t_max")
        t_max_label.setStyleSheet("color: white;")
        t_max_row.addWidget(t_max_label)
        t_max_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        t_max_slider.setRange(1, 500)
        t_max_slider.setValue(config.time_defaults["t_max"])
        t_max_slider.param_step = 1
        t_max_spin = QtWidgets.QSpinBox()
        t_max_spin.setKeyboardTracking(False)
        t_max_spin.setRange(1, 5000)
        t_max_spin.setSingleStep(1)
        t_max_spin.setValue(config.time_defaults["t_max"])
        t_max_spin.param_step = 1
        t_max_slider.valueChanged.connect(
            lambda val: t_max_spin.setValue(val * t_max_slider.param_step)
        )
        t_max_slider.valueChanged.connect(lambda: self.solve_requested.emit(False))
        t_max_slider.sliderReleased.connect(lambda: self.solve_requested.emit(True))
        t_max_spin.valueChanged.connect(
            lambda val: t_max_slider.setValue(int(val / t_max_spin.param_step))
        )
        t_max_spin.valueChanged.connect(self.t_max_changed.emit)
        t_max_row.addWidget(t_max_slider)
        t_max_row.addWidget(t_max_spin)
        self.t_max_slider_wrapper = QtWidgets.QWidget()
        self.t_max_slider_wrapper.setLayout(t_max_row)
        self.panel_layout.addWidget(self.t_max_slider_wrapper)

    def _build_param_sliders(self, config):
        for p in config.params:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(p.name)
            label.setStyleSheet(SLIDER_PARAMS)
            row.addWidget(label)
            s = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            s.setRange(int(p.min_val / p.step), int(p.max_val / p.step))
            s.setValue(int(p.default / p.step))
            s.param_step = p.step
            spin = QtWidgets.QDoubleSpinBox()
            spin.setKeyboardTracking(False)
            spin.setRange(p.min_val, p.max_val)
            spin.setSingleStep(p.step)
            spin.setValue(p.default)
            spin.param_step = p.step
            s.valueChanged.connect(
                lambda val, ss=s, sp=spin: sp.setValue(val * ss.param_step)
            )
            s.valueChanged.connect(lambda: self.solve_requested.emit(False))
            s.sliderReleased.connect(lambda: self.solve_requested.emit(True))
            spin.valueChanged.connect(
                lambda val, ss=s, sp=spin: ss.setValue(int(val / sp.param_step))
            )
            row.addWidget(s)
            row.addWidget(spin)
            wrapper = QtWidgets.QWidget()
            wrapper.setLayout(row)
            self.panel_layout.addWidget(wrapper)
            self.slider_rows.append((p, s, row, wrapper))

    def hide_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(False)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(False)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(False)

    def show_standard_controls(self):
        for _, _, _, wrapper in self.slider_rows:
            wrapper.setVisible(True)
        if self.n_slider_wrapper is not None:
            self.n_slider_wrapper.setVisible(True)
        if self.t_max_slider_wrapper is not None:
            self.t_max_slider_wrapper.setVisible(True)

    def get_current_values(self):
        return {p.name: p.step * s.value() for p, s, _, _ in self.slider_rows}

    def update_projections(self, x, y, z):
        for key, (data_h, data_v) in {"XY": (x, y), "XZ": (x, z), "YZ": (y, z)}.items():
            img, pw = self.image_items[key]
            heatmap, xedges, yedges = np.histogram2d(
                data_h, data_v, bins=N_BINS, density=True
            )
            img.setImage(np.log1p(heatmap))
            x_min, x_max = xedges[0], xedges[-1]
            y_min, y_max = yedges[0], yedges[-1]
            img.setRect(
                pg.QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
            )
            pw.autoRange()

    def reapply_projections(self, solutions):
        if solutions:
            all_sol = np.concatenate(solutions, axis=0)
            x, y, z = all_sol.T
            self.update_projections(x, y, z)
