# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import functools
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.expression_parser import CONSTANTS, FUNCTIONS, ParseError, compile_function
from ..ui.style import plot_colours
from .explorer import PLOT_MODE_OVERLAY

COLOUR_MAPS = pg.colormap.listMaps(source="matplotlib")


@dataclass(frozen=True)
class Kind:
    label: str
    view: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int


# use a and b params so there's sliders to use by default
# TODO: add presets like 3d curve, surface, heatmaps etc.
KINDS = {
    "function": Kind(
        "Function y = f(x)", "plot", {"y": "a * sin(b * x)"}, {"x": (-10.0, 10.0)}, 1000
    ),
}


@dataclass
class SliderItem:
    name: str
    value: float = 1.0
    start: float = -10.0
    end: float = 10.0
    step: float = 0.01


@dataclass
class TraceItem:
    kind: str
    name: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int
    # colour or cmap name
    style: str


def new_trace_item(kind, name, colour_index=0):
    spec = KINDS[kind]
    if kind == "heatmap":
        style = COLOUR_MAPS[0]
    else:
        pens = plot_colours()["plot_auto_pens"]
        style = pg.mkColor(pens[colour_index % len(pens)]).name()

    return TraceItem(
        kind, name, dict(spec.expressions), dict(spec.ranges), spec.samples, style
    )


def evaluate(explorer, func, params, domain):
    values = explorer.params()
    for name in params:
        if name not in values:
            raise ValueError(f"No slider named {name!r}")

    # numpy scalars give inf/nan rather instead of raising so allows the plot checks to report them
    with np.errstate(all="ignore"):
        result = func(**domain, **{name: np.float64(values[name]) for name in params})

    return np.broadcast_to(result, next(iter(domain.values())).shape)


def apply_slider(explorer, item):
    if not item.name.isidentifier():
        raise ValueError("Slider names must be a single word to use in expressions")
    if item.end <= item.start:
        raise ValueError("Slider maximum must be greater than its minimum")

    explorer.slider(item.name, item.value, item.start, item.end, item.step)
    explorer.refresh()


def apply_trace(explorer, item):
    variables = tuple(item.ranges)
    compiled = {
        output: compile_function(expr, variables)
        for output, expr in item.expressions.items()
    }

    existing = set(explorer.slider_names())
    names = [name for _func, params in compiled.values() for name in params]
    sliders = [
        SliderItem(name) for name in dict.fromkeys(names) if name not in existing
    ]
    for slider in sliders:
        explorer.slider(
            slider.name, slider.value, slider.start, slider.end, slider.step
        )

    axes = [np.linspace(lo, hi, item.samples) for lo, hi in item.ranges.values()]
    domain = dict(zip(variables, np.meshgrid(*axes), strict=True))
    f = {
        output: functools.partial(evaluate, explorer, func, params, domain)
        for output, (func, params) in compiled.items()
    }

    name = item.name
    mode = PLOT_MODE_OVERLAY
    match item.kind:
        case "function":
            explorer.curve(name, domain["x"], f["y"], mode=mode, pen=item.style)
        case "parametric":
            explorer.curve(name, f["x"], f["y"], mode=mode, pen=item.style)
        case "points":
            explorer.scatter(
                name,
                f["x"],
                f["y"],
                mode=mode,
                pen=None,
                symbol_size=6,
                symbolBrush=item.style,
                symbolPen=None,
            )
        case "heatmap":
            (x0, x1), (y0, y1) = item.ranges.values()
            explorer.image(
                name, f["z"], extent=(x0, x1, y0, y1), cmap=item.style, mode=mode
            )
        case "curve3d":
            explorer.line3d(
                name, f["x"], f["y"], f["z"], mode=mode, colour=item.style, width=2
            )
        case "points3d":
            explorer.scatter3d(
                name, f["x"], f["y"], f["z"], mode=mode, colour=item.style, size=6
            )
        case "surface":
            explorer.surface3d(
                name, domain["x"], domain["y"], f["z"], mode=mode, colour=item.style
            )

    return sliders


def item_key(item):
    return ("slider" if isinstance(item, SliderItem) else "trace", item.name)


class ColourButton(QtWidgets.QPushButton):
    def __init__(self, colour, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.clicked.connect(self._choose)
        self.colour = colour
        self.setStyleSheet(f"ColourButton {{background-color: {colour}}};")

    def _choose(self):
        dialog = QtWidgets.QColorDialog()
        colour = dialog.getColor(pg.mkColor(self.colour), self, "Choose colour")
        if colour.isValid():
            self.colour = colour.name()


def spin_box(value, *, decimals=4, minimum=-1e6):
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(minimum, 1e6)
    spin.setDecimals(decimals)
    spin.setValue(value)

    return spin


class ItemEditor(QtWidgets.QWidget):
    apply_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.form = QtWidgets.QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self._item = None
        self._fields = {}

    def load(self, item):
        while self.form.rowCount():
            self.form.removeRow(0)

        self._item = item
        self._fields = {}
        if item is None:
            return

        self._add_line("Name", "name", item.name)
        if isinstance(item, SliderItem):
            for label, attr in (
                ("Value", "value"),
                ("Minimum", "start"),
                ("Maximum", "end"),
            ):
                self._add_field(label, attr, spin_box(getattr(item, attr)))
            self._add_field("Step", "step", spin_box(item.step, minimum=1e-4))

            return

        for output, expr in item.expressions.items():
            self._add_line(f"{output} =", ("expr", output), expr)

        for variable, (lo, hi) in item.ranges.items():
            self._add_field(f"{variable} from", ("range", variable, "lo"), spin_box(lo))
            self._add_field(f"{variable} to", ("range", variable, "hi"), spin_box(hi))

        samples = QtWidgets.QSpinBox()
        samples.setRange(2, 1_000_000)
        samples.setValue(item.samples)
        per_axis = " per axis" if len(item.ranges) > 1 else ""
        self._add_field(f"Samples{per_axis}", "samples", samples)

        if item.kind == "heatmap":
            combo = QtWidgets.QComboBox()
            combo.addItems(COLOUR_MAPS)
            combo.setCurrentText(item.style)
            combo.setMaxVisibleItems(12)
            combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
            self._add_field("Colour map", "style", combo)
        else:
            self._add_field("Colour", "style", ColourButton(item.style))

    def _add_field(self, label, key, widget):
        self._fields[key] = widget
        self.form.addRow(label, widget)

    def _add_line(self, label, key, text):
        edit = QtWidgets.QLineEdit(text)
        edit.returnPressed.connect(self.apply_requested)
        self._add_field(label, key, edit)

    def item(self):
        """The loaded item with the form's current values"""
        fields = self._fields
        name = fields["name"].text().strip()
        if isinstance(self._item, SliderItem):
            return SliderItem(
                name,
                fields["value"].value(),
                fields["start"].value(),
                fields["end"].value(),
                fields["step"].value(),
            )

        style = fields["style"]
        return TraceItem(
            self._item.kind,
            name,
            {
                output: fields[("expr", output)].text()
                for output in self._item.expressions
            },
            {
                variable: (
                    fields[("range", variable, "lo")].value(),
                    fields[("range", variable, "hi")].value(),
                )
                for variable in self._item.ranges
            },
            fields["samples"].value(),
            style.currentText()
            if isinstance(style, QtWidgets.QComboBox)
            else style.colour,
        )


class BuilderPanel(QtWidgets.QWidget):
    def __init__(self, console_panel, parent=None):
        super().__init__(parent)
        self._console_panel = console_panel
        self._explorer = None
        # build items per explorer and get key with item_key()
        self._items = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.target_label = QtWidgets.QLabel()
        layout.addWidget(self.target_label)

        buttons = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QToolButton()
        self.add_button.setText("Add")
        self.add_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.add_menu = QtWidgets.QMenu(self.add_button)
        self.add_menu.triggered.connect(lambda action: self.add(action.data()))
        self.add_button.setMenu(self.add_menu)
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.item_list = QtWidgets.QListWidget()
        self.item_list.currentItemChanged.connect(self._load_selected)

        edit_host = QtWidgets.QWidget()
        edit_layout = QtWidgets.QVBoxLayout(edit_host)
        edit_layout.setContentsMargins(0, 4, 0, 0)

        self.editor = ItemEditor()
        self.editor.apply_requested.connect(self.apply_edit)
        edit_layout.addWidget(self.editor)

        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_edit)
        edit_layout.addWidget(self.apply_button)

        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        self.error_label.hide()
        edit_layout.addWidget(self.error_label)

        help_label = QtWidgets.QLabel(
            "Write expressions with +, -, *, /, ** and "
            f"{', '.join(FUNCTIONS)}. Constants: {', '.join(CONSTANTS)}. "
            "Any other name becomes a slider."
        )
        help_label.setWordWrap(True)
        help_label.setEnabled(False)
        edit_layout.addWidget(help_label)
        edit_layout.addStretch(1)

        edit_scroll = QtWidgets.QScrollArea()
        edit_scroll.setWidgetResizable(True)
        edit_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        edit_scroll.setWidget(edit_host)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.item_list)
        splitter.addWidget(edit_scroll)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        console_panel.active_view_changed.connect(self.sync)
        for manager in (console_panel.plots, console_panel.views3d):
            manager.current_changed.connect(lambda _name: self.sync())
            manager.views_changed.connect(self.sync)
            manager.view_removed.connect(
                lambda _name, view: self._items.pop(view.explore, None)
            )
        self.sync()

    def items(self):
        return self._items.setdefault(self._explorer, {})

    def sync(self):
        explorer = self._console_panel.active_explorer()
        if explorer is not self._explorer:
            if self._explorer is not None:
                self._explorer.changed.disconnect(self._prune)
            self._explorer = explorer
            explorer.changed.connect(self._prune)

        kind, name = self._console_panel.active_view_key()
        self.target_label.setText(
            f"Adding to: {'3D view' if kind == 'view3d' else 'plot'} {name!r}"
        )

        self.add_menu.clear()
        self.add_menu.addAction("Slider").setData("slider")
        self.add_menu.addSeparator()
        for key, spec in KINDS.items():
            if spec.view == kind:
                self.add_menu.addAction(spec.label).setData(key)

        self._prune()

    def add(self, kind):
        explorer = self._explorer
        if kind == "slider":
            item = SliderItem(self._unique_name("s", explorer.slider_names(), sep=""))
        else:
            traces = sum(isinstance(item, TraceItem) for item in self.items().values())
            item = new_trace_item(
                kind, self._unique_name(kind, explorer.trace_names(), sep=" "), traces
            )

        if self._apply(item):
            self._select(item)
