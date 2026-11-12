# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import functools

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .animation import ConsoleAnimation, ConsoleAnimationWidget

PLOT_MODE_REPLACE = "replace"
PLOT_MODE_OVERLAY = "overlay"


def parse_mode(mode):
    normalised = str(mode).strip().lower()
    if normalised not in (PLOT_MODE_REPLACE, PLOT_MODE_OVERLAY):
        raise ValueError("Plot mode must be 'replace' or 'overlay'")

    return normalised


def resolve(value):
    return value() if callable(value) else value


def line_kwargs(pen=None, label=None):
    kwargs = {}
    if pen is not None:
        kwargs["pen"] = pen
    if label is not None:
        kwargs["name"] = str(label)

    return kwargs


def check_array_dim(value, name):
    data = np.asarray(value, dtype=np.float64)

    if data.ndim != 1:
        raise ValueError(f"{name} must be one dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{name} contains non finite values")

    return data


def check_xy(x, y):
    x_array = check_array_dim(resolve(x), "x")
    y_array = check_array_dim(resolve(y), "y")
    if len(x_array) != len(y_array):
        raise ValueError("x and y must be the same length")

    return x_array, y_array


def check_scalar(value, name):
    value = np.asarray(value, dtype=np.float64)

    if value.shape != ():
        raise ValueError(f"{name} must be a scalar")
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")

    return float(value)


def check_bins(value):
    value = resolve(value)

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


def dispose(control, layout):
    layout.removeWidget(control.widget)
    control.widget.deleteLater()
    control.deleteLater()


def control_key(name, kind):
    key = str(name).strip()
    if not key:
        raise ValueError(f"{kind} name cannot be empty")

    return key


class ExplorerControls(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self, param_widget, param_layout, status_callback=None, parent=None):
        super().__init__(parent)
        self.param_widget = param_widget
        self.param_layout = param_layout
        self.status_callback = status_callback
        self._params = {}
        self._animations = {}
        self._traces = {}

    def slider(self, name, value=0.0, start=0.0, end=1.0, step=0.01):
        key = control_key(name, "Slider")
        old = self._params.pop(key, None)
        if old is not None:
            dispose(old, self.param_layout)

        param = ConsoleParam(key, value, start, end, step, parent=self)
        param.changed.connect(self.refresh)
        self._params[key] = param
        self.param_layout.addWidget(param.widget)
        self.param_widget.setVisible(True)
        self.changed.emit()

        return param

    def int_slider(self, name, value=0, start=0, end=100, step=1):
        # useful for when setting sliders to array sizes
        return self.slider(name, int(value), int(start), int(end), int(step))

    def animation(
        self,
        name,
        callback,
        *,
        interval=16,
        dt=None,
        frames=None,
        loop=False,
        start=False,
    ):
        key = control_key(name, "Animation")
        old = self._animations.pop(key, None)
        if old is not None:
            old.pause()
            dispose(old, self.param_layout)

        animation = ConsoleAnimation(
            key,
            callback,
            interval=interval,
            dt=dt,
            frames=frames,
            loop=loop,
            status_callback=self.status_callback,
            parent=self,
        )
        widget = ConsoleAnimationWidget(animation)
        animation.widget = widget

        self._animations[key] = animation
        self.param_layout.addWidget(widget)
        self.param_widget.setVisible(True)
        self.changed.emit()

        if start:
            animation.play()

        return animation

    def params(self):
        return {name: param.value for name, param in self._params.items()}

    def animations(self):
        return {
            name: {
                "name": animation.name,
                "interval": animation.interval,
                "frame": animation.frame,
                "active": animation.is_active(),
            }
            for name, animation in self._animations.items()
        }

    def slider_names(self):
        return list(self._params)

    def trace_names(self):
        return list(self._traces)

    def animation_names(self):
        return list(self._animations)

    def has_controls(self):
        return bool(self._params or self._animations)

    def remove_slider(self, name):
        key = str(name).strip()
        param = self._params.pop(key, None)
        if param is None:
            raise KeyError(f"No slider named {key!r}")

        dispose(param, self.param_layout)
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

        return self.params()

    def remove_animation(self, name):
        key = str(name).strip()
        animation = self._animations.pop(key, None)
        if animation is None:
            raise KeyError(f"No animation named {key!r}")

        animation.pause()
        dispose(animation, self.param_layout)
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

        return self.animations()

    def remove_trace(self, name):
        key = str(name).strip()
        trace = self._traces.pop(key, None)
        if trace is None:
            raise KeyError(f"No trace named {key!r}")

        trace.remove()
        self._sync_trace_menu()
        self.changed.emit()

        return self.traces()

    def refresh(self):
        updated = False
        for trace in list(self._traces.values()):
            try:
                trace.update()
                updated = True
            except (TypeError, ValueError, FloatingPointError) as exc:
                self._set_status(f"{trace.name}: {exc}", error=True)

        return updated

    def clear(self):
        self.clear_animations()
        self.clear_sliders()
        self.clear_traces()

    def clear_traces(self):
        for trace in list(self._traces.values()):
            trace.remove()

        self._traces.clear()
        self._sync_trace_menu()
        self.changed.emit()

    def clear_sliders(self):
        for param in self._params.values():
            dispose(param, self.param_layout)

        self._params.clear()
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

    def clear_animations(self):
        for animation in self._animations.values():
            animation.pause()
            dispose(animation, self.param_layout)

        self._animations.clear()
        self.param_widget.setVisible(self.has_controls())
        self.changed.emit()

    def _new_trace_key(self, name):
        key = control_key(name, "Trace")
        old = self._traces.pop(key, None)
        if old is not None:
            old.remove()

        return key

    def _store_trace(self, key, trace):
        self._traces[key] = trace
        self._sync_trace_menu()
        self.changed.emit()

        return trace

    def _sync_trace_menu(self):
        """Hook for explorers that list their traces in a menu"""

    def _set_status(self, message, *, error=False):
        if self.status_callback is not None:
            self.status_callback(message, error=error)


class ConsoleTrace:
    def __init__(self, name, item, plot, update_callback, data_provider=None):
        self.name = name
        self.item = item
        self.plot = plot
        self.update_callback = update_callback
        self.data_provider = data_provider

    def update(self):
        self.update_callback(self.item)

    def remove(self):
        if self.item.scene() is None:
            return

        self.plot._plot_widget.removeItem(self.item)

    def data(self):
        if self.data_provider is None:
            raise ValueError(f"Trace {self.name!r} has no point data")

        return self.data_provider()


class PlotExplorer(ExplorerControls):
    def __init__(
        self,
        plot,
        param_widget,
        param_layout,
        trace_menu,
        status_callback=None,
        parent=None,
    ):
        super().__init__(param_widget, param_layout, status_callback, parent)
        self.plot = plot
        self.trace_menu = trace_menu
        self._sync_trace_menu()

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

    def traces(self):
        return {name: trace.name for name, trace in self._traces.items()}

    def _data_trace_update(self, x, y):
        return functools.partial(self._update_trace_data, x, y)

    def _update_trace_data(self, x, y, item):
        x_array, y_array = check_xy(x, y)
        item.setData(x=x_array, y=y_array)

    def _update_hist_data(self, values, bins, density, item):
        x_array, y_array = hist_step(resolve(values), bins, density=density)
        item.setData(x=x_array, y=y_array)

    def _trace_data(self, name, item):
        x_array, y_array = check_xy(*item.getData())

        return {
            "trace": np.full(len(x_array), name),
            "index": np.arange(len(x_array)),
            "x": x_array,
            "y": y_array,
        }

    def _add_data_trace(self, key, item, update):
        trace = ConsoleTrace(
            key,
            item,
            self.plot,
            update,
            data_provider=functools.partial(self._trace_data, key, item),
        )
        self._connect_trace_data(trace)

        return self._store_trace(key, trace)

    def _connect_trace_data(self, trace):
        trace.item.setCurveClickable(True, width=8)
        trace.item.sigClicked.connect(
            lambda _item, ev, trace=trace: self._trace_clicked(trace, ev)
        )

    def _trace_clicked(self, trace, ev):
        if ev.double():
            return

        self.plot.show_trace_data(trace)

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
        mode = parse_mode(mode)
        x_array, y_array = check_xy(x, y)
        key = self._new_trace_key(name)
        item = self.plot.line(
            x_array, y_array, mode=mode, **{**kwargs, **line_kwargs(pen, label)}
        )

        return self._add_data_trace(
            key, item, functools.partial(self._update_trace_data, x, y)
        )

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
        mode = parse_mode(mode)
        x_array, y_array = check_xy(x, y)
        key = self._new_trace_key(name)
        item = self.plot.scatter(
            x_array,
            y_array,
            mode=mode,
            symbol=symbol,
            symbol_size=symbol_size,
            **{**kwargs, **line_kwargs(label=label)},
        )

        return self._add_data_trace(
            key, item, functools.partial(self._update_trace_data, x, y)
        )

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
        mode = parse_mode(mode)
        x_array, y_array = hist_step(resolve(values), bins, density=density)
        key = self._new_trace_key(name)
        item = self.plot.line(
            x_array, y_array, mode=mode, **{**kwargs, **line_kwargs(pen, label)}
        )

        return self._add_data_trace(
            key,
            item,
            functools.partial(self._update_hist_data, values, bins, density),
        )

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
        line.setValue(check_scalar(resolve(value), value_name))

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

        position = check_scalar(resolve(value), value_name)
        key = self._new_trace_key(name)
        item = pg.InfiniteLine(
            pos=position, angle=angle, movable=movable, **plot_kwargs
        )
        self.plot._plot_widget.addItem(item)

        update = functools.partial(self._update_line, value, value_name)

        return self._store_trace(key, ConsoleTrace(key, item, self.plot, update))
