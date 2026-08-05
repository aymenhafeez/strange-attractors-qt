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
        layout.setSpacing(0)

        label = QtWidgets.QLabel(self.name)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.spin = QtWidgets.QDoubleSpinBox()

        # map the numeric range onto step indices since Qt sliders are integer based
        steps = max(1, round((self.end - self.start) / self.step))
        self.slider.setRange(0, steps)
        self.spin.setRange(self.start, self.end)
        self.spin.setSingleStep(self.step)
        self.spin.setDecimals(6)

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
    """Reactive 2D plot curve. Data recomputed on command"""

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
        self.plot._plot_widget.removeItem(self.item)


class ConsoleExplorer(QtCore.QObject):
    """Manage reactive plots and parameters created in the console"""

    def __init__(self, plots, param_layout, status_callback=None, parent=None):
        super().__init__(parent)
        self.plots = plots
        self.param_layout = param_layout
        self.status_callback = status_callback
        self._params = {}
        self._curves = {}

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

        return param

    def curves(self):
        return {name: curve.name for name, curve in self._curves.items()}

    def params(self):
        return {name: param.value for name, param in self._params.items()}

    def remove_curve(self, name):
        key = str(name).strip()
        curve = self._curves.pop(key, None)
        if curve is None:
            raise KeyError(f"No curve named {key!r}")

        curve.remove()

        return self.curves()

    def remove_slider(self, name):
        key = str(name).strip()
        param = self._params.pop(key, None)
        if param is None:
            raise KeyError(f"No slider named {key!r}")

        self.param_layout.removeWidget(param.widget)
        param.widget.deleteLater()

        return self.params()

    def curve(
        self,
        name,
        x,
        y,
        *,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        label=None,
        pen=None,
        **kwargs,
    ):
        target = self.plots.current if plot is None else self.plots.get(plot)
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

        old = self._curves.pop(str(name), None)
        if old is not None:
            old.remove()

        item = target.line(x_array, y_array, mode=mode, **plot_kwargs)
        curve = ConsoleTrace(name, x, y, item, target)
        self._curves[name] = curve

        return curve

    def scatter(
        self,
        name,
        x,
        y,
        *,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        label=None,
        symbol="o",
        symbol_size=None,
        **kwargs,
    ):
        target = self.plots.current if plot is None else self.plots.get(plot)
        mode = mode.strip().lower()

        if mode not in {PLOT_MODE_REPLACE, PLOT_MODE_OVERLAY}:
            raise ValueError("Plot mode must be either 'replace' or 'overlay'")

        plot_kwargs = kwargs.copy()
        if label is not None:
            plot_kwargs["name"] = str(label)

        x_data = x() if callable(x) else x
        y_data = y() if callable(y) else y
        x_array = np.array(x_data)
        y_array = np.array(y_data)

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        old = self._curves.pop(str(name), None)
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
        curve = ConsoleTrace(name, x, y, item, target)
        self._curves[name] = curve

        return curve

    def refresh(self):
        for curve in list(self._curves.values()):
            try:
                curve.update()
            except (TypeError, ValueError, FloatingPointError) as exc:
                self._set_status(f"{curve.name}: {exc}")

    def clear(self):
        for param in self._params.values():
            self.param_layout.removeWidget(param.widget)
            param.widget.deleteLater()

        for curve in self._curves.values():
            curve.remove()

        self._params.clear()
        self._curves.clear()

    def _set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
