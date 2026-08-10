import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

PLOT_MODE_REPLACE = "replace"
PLOT_MODE_OVERLAY = "overlay"


def check_array_dim(value, name):
    data = np.asarray(value, dtype=np.float64)

    if data.ndim != 1:
        raise ValueError(f"{name} must be one dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{name} contains non finite values")

    return data


class ConsoleParam(QtCore.QObject):
    """Console created parameter backed by a slider and spinbox"""

    changed = QtCore.pyqtSignal()

    def __init__(self, name, value, start, end, step, parent=None):
        super().__init__(parent)
        self.name = name
        self.start = start
        self.end = end
        self.step = step
        self.value = value

        self.widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QtWidgets.QLabel(self.name)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.spin = QtWidgets.QDoubleSpinBox()

        # map the numeric range onto step indices since Qt sliders are integer based
        steps = max(1, round((self.end - self.start) / self.step))
        self.slider.setRange(0, steps)
        self.spin.setRange(self.start, self.end)
        self.spin.setSingleStep(self.step)
        self.spin.setDecimals(6)
        self.spin.setKeyboardTracking(False)

        layout.addWidget(label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

        self.set_value(self.value, emit=False)

        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin.valueChanged.connect(self._on_spin_changed)

    def set_value(self, value, *, emit=True):
        value = min(self.end, max(self.start, float(value)))
        index = round((value - self.start) / self.step)
        snapped = self.start + index * self.step
        self.value = snapped

        # keep the widgets in sync without emitting changes recursively
        with QtCore.QSignalBlocker(self.slider), QtCore.QSignalBlocker(self.spin):
            self.slider.setValue(index)
            self.spin.setValue(snapped)

        if emit:
            self.changed.emit()

    def _on_slider_changed(self, index):
        self.set_value(self.start + index * self.step)

    def _on_spin_changed(self, value):
        self.set_value(value)

    def __float__(self):
        return self.value

    def __repr__(self):
        return f"ConsoleParam({self.name!r}, value={self.value:g})"


class ConsoleTrace:
    """Reactive 2D plot item. Data recomputed on command"""

    def __init__(self, name, x, y, item, plot):
        self.name = name
        self.x = x
        self.y = y
        self.item = item
        self.plot = plot

    def update(self):
        # callable for reactive plots, otherwise static
        x_data = self.x() if callable(self.x) else self.x
        y_data = self.y() if callable(self.y) else self.y
        x_array = check_array_dim(x_data, "x")
        y_array = check_array_dim(y_data, "y")

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        self.item.setData(x_array, y_array)

    def remove(self):
        if self.plot.has_item(self.item):
            self.plot._plot_widget.removeItem(self.item)


class PlotExplorer(QtCore.QObject):
    """Manage reactive plots and parameters for a single console plot"""

    def __init__(
        self,
        plot,
        param_widget,
        param_layout,
        trace_controls_layout,
        status_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.plot = plot
        self.param_widget = param_widget
        self.param_layout = param_layout
        self.trace_controls_layout = trace_controls_layout
        self.status_callback = status_callback
        self._params = {}
        self._traces = {}
        self._trace_widgets = {}

    def _add_trace_widget(self, name):
        old = self._trace_widgets.pop(name, None)
        if old is not None:
            self.trace_controls_layout.removeWidget(old)
            old.deleteLater()

        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QtWidgets.QLabel(name)
        remove = QtWidgets.QToolButton()
        remove.setText("x")
        remove.setToolTip(f"Remove trace {name!r}")
        remove.clicked.connect(
            lambda _checked=False, trace_name=name: self.remove_trace(trace_name)
        )

        layout.addWidget(label, 1)
        layout.addWidget(remove)

        self._trace_widgets[name] = row
        self.trace_controls_layout.addWidget(row)

    def _remove_trace_widget(self, name):
        row = self._trace_widgets.pop(name, None)
        if row is not None:
            self.trace_controls_layout.removeWidget(row)
            row.deleteLater()

    def slider(self, name, value=0.0, start=0.0, end=1.0, step=0.01):
        key = name.strip()
        if not key:
            raise ValueError("Slider key cannot be empty")

        old = self._params.pop(key, None)
        if old is not None:
            self.param_layout.removeWidget(old.widget)
            old.widget.deleteLater()

        param = ConsoleParam(key, value, start, end, step, parent=self)
        param.changed.connect(self.refresh)
        self._params[key] = param
        self.param_layout.addWidget(param.widget)
        self.param_widget.setVisible(True)

        return param

    def int_slider(self, name, value=0, start=0, end=100, step=1):
        # useful for when setting sliders to array sizes
        return self.slider(
            name, value=int(value), start=int(start), end=int(end), step=int(step)
        )

    def traces(self):
        return {name: trace.name for name, trace in self._traces.items()}

    def params(self):
        return {name: param.value for name, param in self._params.items()}

    def remove_trace(self, name):
        key = str(name).strip()
        trace = self._traces.pop(key, None)
        if trace is None:
            raise KeyError(f"No trace named {key!r}")

        trace.remove()
        self._remove_trace_widget(key)

        return self.traces()

    def remove_slider(self, name):
        key = str(name).strip()
        param = self._params.pop(key, None)
        if param is None:
            raise KeyError(f"No slider named {key!r}")

        self.param_layout.removeWidget(param.widget)
        param.widget.deleteLater()
        self.param_widget.setVisible(bool(self._params))

        return self.params()

    # TODO: write a helper around curve() and scatter()
    def curve(
        self,
        name,
        x,
        y,
        *,
        mode=PLOT_MODE_REPLACE,
        label=None,
        pen=None,
        **kwargs,
    ):
        target = self.plot
        mode = mode.strip().lower()

        if mode not in {PLOT_MODE_REPLACE, PLOT_MODE_OVERLAY}:
            raise ValueError("Plot mode must be either 'replace' or 'overlay'")

        plot_kwargs = kwargs.copy()
        if pen is not None:
            plot_kwargs["pen"] = pen
        if label is not None:
            plot_kwargs["name"] = str(label)

        x_data = x() if callable(x) else x
        y_data = y() if callable(y) else y
        x_array = check_array_dim(x_data, "x")
        y_array = check_array_dim(y_data, "y")

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        old = self._traces.pop(str(name), None)
        if old is not None:
            old.remove()

        item = target.line(x_array, y_array, mode=mode, **plot_kwargs)
        trace = ConsoleTrace(name, x, y, item, target)
        self._traces[name] = trace
        self._add_trace_widget(name)

        return trace

    def scatter(
        self,
        name,
        x,
        y,
        *,
        mode=PLOT_MODE_REPLACE,
        label=None,
        symbol="o",
        symbol_size=None,
        **kwargs,
    ):
        target = self.plot
        mode = mode.strip().lower()

        if mode not in {PLOT_MODE_REPLACE, PLOT_MODE_OVERLAY}:
            raise ValueError("Plot mode must be either 'replace' or 'overlay'")

        plot_kwargs = kwargs.copy()
        if label is not None:
            plot_kwargs["name"] = str(label)

        x_data = x() if callable(x) else x
        y_data = y() if callable(y) else y
        x_array = check_array_dim(x_data, "x")
        y_array = check_array_dim(y_data, "y")

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        old = self._traces.pop(str(name), None)
        if old is not None:
            old.remove()

        item = target.scatter(
            x_array,
            y_array,
            mode=mode,
            symbol=symbol,
            symbol_size=symbol_size,
            **plot_kwargs,
        )
        trace = ConsoleTrace(name, x, y, item, target)
        self._traces[name] = trace
        self._add_trace_widget(name)
        return trace

    def refresh(self):
        for trace in list(self._traces.values()):
            try:
                trace.update()
            except (TypeError, ValueError, FloatingPointError) as exc:
                self._set_status(f"{trace.name}: {exc}")

    def clear(self):
        self.clear_sliders()
        self.clear_traces()

    def clear_traces(self):
        for trace in self._traces.values():
            trace.remove()

        self._traces.clear()

        for row in self._trace_widgets.values():
            self.trace_controls_layout.removeWidget(row)
            row.deleteLater()

        self._trace_widgets.clear()

    def clear_sliders(self):
        for param in self._params.values():
            self.param_layout.removeWidget(param.widget)
            param.widget.deleteLater()

        self._params.clear()
        self.param_widget.setVisible(False)

    def _set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
