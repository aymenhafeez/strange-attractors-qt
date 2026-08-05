import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets


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

        steps = max(1, round((self.end - self.start) / self.step))
        self.slider.setRange(0, steps)
        self.spin.setRange(self.start, self.end)
        self.spin.setSingleStep(self.step)
        self.spin.setDecimals(6)

        layout.addWidget(label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

        self.set_value(self.value, emit=False)

    def set_value(self, value, *, emit=True):
        value = min(self.end, max(self.start, float(value)))
        index = round((value - self.start) / self.step)
        snapped = self.start + index * self.step
        self.value = snapped

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


class ConsoleCurve:
    """Reactive 2D plot curve. Data recomputed on command"""

    def __init__(self, name, x, y, item, plot):
        self.name = name
        self.x = x
        self.y = y
        self.item = item
        self.plot = plot

    def update(self):
        x_data = self.x() if callable(self.x) else self.x
        y_data = self.y() if callable(self.y) else self.y
        x_array = np.array(x_data)
        y_array = np.array(y_data)

        if len(x_array) != len(y_array):
            raise ValueError("x and y must be the same length")

        self.item.setData(x_array, y_array)


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

    def refresh(self):
        for curve in list(self._curves.values()):
            try:
                curve.update()
            except Exception as e:
                self._set_status(str(e))

    def _set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)
