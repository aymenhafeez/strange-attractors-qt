import functools

import numpy as np
import pyqtgraph as pg
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


def check_scalar(value, name):
    value = np.asarray(value, dtype=np.float64)

    if value.shape != ():
        raise ValueError(f"{name} must be a scalar")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")

    return float(value)


def check_bins(value):
    value = value() if callable(value) else value

    if np.isscalar(value):
        bins = int(value)
        if bins < 1:
            raise ValueError("N bins must be atleast 1")
        return bins

    bins = check_array_dim(value, "bins")
    if len(bins) < 2:
        raise ValueError("bins must have atleast 2 edges")
    if not np.all(np.diff(bins) > 0):
        raise ValueError("bins must be increasing")

    return bins


def hist_step(values, bins, *, density=False):
    values = check_array_dim(values, "values")
    bins = check_bins(bins)
    counts, edges = np.histogram(values, bins=bins, density=density)

    x = np.repeat(edges, 2)[1:-1]
    y = np.repeat(counts, 2)

    return x, y


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

    def __init__(self, name, item, plot, update_callback):
        self.name = name
        self.item = item
        self.plot = plot
        self.update_callback = update_callback

    def update(self):
        self.update_callback(self.item)

    def remove(self):
        if self.plot.has_item(self.item):
            self.plot._plot_widget.removeItem(self.item)


class PlotExplorer(QtCore.QObject):
    """Manage reactive plots and parameters for a single console plot"""

    changed = QtCore.pyqtSignal()

    def __init__(
        self,
        plot,
        param_widget,
        param_layout,
        trace_menu,
        status_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.plot = plot
        self.param_widget = param_widget
        self.param_layout = param_layout
        self.trace_menu = trace_menu
        self.status_callback = status_callback
        self._params = {}
        self._traces = {}
        self._sync_trace_menu()

    def trace_names(self):
        return list(self._traces)

    def slider_names(self):
        return list(self._params)

    def _sync_trace_menu(self):
        self.trace_menu.clear()

        if not self._traces:
            action = self.trace_menu.addAction("No traces")
            action.setEnabled(False)
            return

        for name in self._traces:
            action = self.trace_menu.addAction(name)
            action.setToolTip(f"Remove trace {name!r}")
            action.triggered.connect(
                lambda checked=False, name=name: self.remove_trace(name)
            )

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
        self.changed.emit()

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
        self._sync_trace_menu()
        self.changed.emit()

        return self.traces()

    def remove_slider(self, name):
        key = str(name).strip()
        param = self._params.pop(key, None)
        if param is None:
            raise KeyError(f"No slider named {key!r}")

        self.param_layout.removeWidget(param.widget)
        param.widget.deleteLater()
        self.param_widget.setVisible(bool(self._params))
        self.changed.emit()

        return self.params()

    def _replace_trace(self, name, trace):
        key = str(name).strip()

        if not key:
            raise ValueError("Trace name cannot be empty")

        old = self._traces.pop(key, None)

        if old is not None:
            old.remove()

        self._traces[key] = trace
        self._sync_trace_menu()
        self.changed.emit()

        return trace

    def _data_trace_update(self, x, y):
        return functools.partial(self._update_trace_data, x, y)

    def _update_trace_data(self, x, y, item):
        x_data = x() if callable(x) else x
        y_data = y() if callable(y) else y
        x_array = check_array_dim(x_data, "x")
        y_array = check_array_dim(y_data, "y")

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        item.setData(x=x_array, y=y_array)

    def _hist_trace_update(self, values, bins, density):
        return functools.partial(self._update_hist_data, values, bins, density)

    def _update_hist_data(self, values, bins, density, item):
        values_data = values() if callable(values) else values
        x_array, y_array = hist_step(values_data, bins, density=density)

        item.setData(x=x_array, y=y_array)

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

        item = target.line(x_array, y_array, mode=mode, **plot_kwargs)
        trace = ConsoleTrace(name, item, target, self._data_trace_update(x, y))

        return self._replace_trace(name, trace)

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

        item = target.scatter(
            x_array,
            y_array,
            mode=mode,
            symbol=symbol,
            symbol_size=symbol_size,
            **plot_kwargs,
        )
        trace = ConsoleTrace(name, item, target, self._data_trace_update(x, y))

        return self._replace_trace(name, trace)

    # TODO: add brush and fill bars rather than a simple step curve
    def hist(
        self,
        name,
        values,
        *,
        bins=50,
        density=False,
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

        values_data = values() if callable(values) else values
        x_array, y_array = hist_step(values_data, bins, density=density)

        item = target.line(x_array, y_array, mode=mode, **plot_kwargs)
        trace = ConsoleTrace(
            name, item, target, self._hist_trace_update(values, bins, density)
        )

        return self._replace_trace(name, trace)

    def vline(self, name, x, *, pen=None, label=None, movable=False, **kwargs):
        return self.line(
            name,
            x,
            angle=90,
            value_name="x",
            pen=pen,
            label=label,
            movable=movable,
            **kwargs,
        )

    def hline(self, name, y, *, pen=None, label=None, movable=False, **kwargs):
        return self.line(
            name,
            y,
            angle=0,
            value_name="y",
            pen=pen,
            label=label,
            movable=movable,
            **kwargs,
        )

    def _update_line(self, value, value_name, line):
        raw_value = value() if callable(value) else value
        line.setValue(check_scalar(raw_value, value_name))

    def line(
        self,
        name,
        value,
        *,
        angle,
        value_name,
        pen=None,
        label=None,
        movable=False,
        **kwargs,
    ):
        plot_kwargs = kwargs.copy()
        if pen is not None:
            plot_kwargs["pen"] = pen
        if label is not None:
            plot_kwargs["label"] = str(label)

        raw_value = value() if callable(value) else value
        item = pg.InfiniteLine(
            pos=check_scalar(raw_value, value_name),
            angle=angle,
            movable=movable,
            **plot_kwargs,
        )
        self.plot._plot_widget.addItem(item)

        update = functools.partial(self._update_line, value, value_name)
        trace = ConsoleTrace(name, item, self.plot, update)

        return self._replace_trace(name, trace)

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
        self._sync_trace_menu()
        self.changed.emit()

    def clear_sliders(self):
        for param in self._params.values():
            self.param_layout.removeWidget(param.widget)
            param.widget.deleteLater()

        self._params.clear()
        self.changed.emit()
        self.param_widget.setVisible(bool(self._params))

    def _set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
