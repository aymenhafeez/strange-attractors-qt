import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..core.signal_analysis import prepare_signal
from .style import PANEL_SURFACE, plot_colours


class SignalPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = None
        self.signal = None
        self.selected_signal = None
        self._interval = None

        self.setObjectName("panelSurface")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PANEL_SURFACE)

        self.trajectory_combo = QtWidgets.QComboBox()
        self.coordinate_combo = QtWidgets.QComboBox()
        self.trajectory_combo.setEnabled(False)
        self.coordinate_combo.setEnabled(False)

        source_row = QtWidgets.QHBoxLayout()
        source_row.addWidget(QtWidgets.QLabel("Trajectory"))
        source_row.addWidget(self.trajectory_combo, 1)
        source_row.addWidget(QtWidgets.QLabel("Coordonate"))
        source_row.addWidget(self.coordinate_combo)

        self.status_label = QtWidgets.QLabel("No completed run")
        self.status_label.setWordWrap(True)
        self.info_label = QtWidgets.QLabel("No completed run")
        self.info_label.setWordWrap(True)

        self.trace = pg.PlotWidget()
        self.trace.setLabel("bottom", "Time")
        self.curve = self.trace.plot()
        self.curve.setDownsampling(auto=True, method="peak")
        self.curve.setClipToView(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        layout.addLayout(source_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.trace, 1)
        layout.addWidget(self.info_label)

        self.trajectory_combo.currentIndexChanged.connect(self._show_trace)
        self.coordinate_combo.currentIndexChanged.connect(self._show_trace)
        self.apply_theme()

    def set_source(self, run, state):
        fresh = (
            run is not None
            and state.get("valid")
            and not state.get("stale")
            and not state.get("solving")
            and state.get("request_id") == run["request_id"]
        )

        if state.get("last_error"):
            text = f"Solve failed: {state['last_error']}"
        elif state.get("solving"):
            text = "Solving"
        elif run is None:
            text = "No completed run"
        elif fresh:
            text = "Completed run"
        else:
            text = "Settings changed"

        if run is not None and not fresh:
            text += " - showing previous completed run"
        self.status_label.setText(text)

        if run is self._run:
            return

        trajectory = max(self.trajectory_combo.currentIndex(), 0)
        coordinate = self.coordinate_combo.currentText()
        self._run = run

        with (
            QtCore.QSignalBlocker(self.trajectory_combo),
            QtCore.QSignalBlocker(self.coordinate_combo),
        ):
            self.trajectory_combo.clear()
            self.coordinate_combo.clear()

            if run is not None:
                for label, spec in zip(run["labels"], run["trajectory_specs"]):
                    initial = ", ".join(f"{v:g}" for v in spec["ic"])
                    self.trajectory_combo.addItem(f"{label}: ({initial})")

                self.trajectory_combo.setCurrentIndex(
                    min(trajectory, self.trajectory_combo.count() - 1)
                )
                self.coordinate_combo.addItems(run["variables"])
                self.coordinate_combo.setCurrentText(
                    coordinate
                    if coordinate in run["variables"]
                    else run["variables"][0]
                )
                parameters = ", ".join(
                    f"{name}={value:g}" for name, value in run["parameters"].items()
                )
                self.trajectory_combo.setToolTip(f"{run['attractor']}\n{parameters}")
            else:
                self.trajectory_combo.setToolTip("")

        self.trajectory_combo.setEnabled(run is not None)
        self.coordinate_combo.setEnabled(run is not None)
        self._show_trace()

    def _show_trace(self):
        self.signal = None
        if self._run is None:
            self.curve.clear()
            self.trace.setLabel("left", "Value")
            self.info_label.clear()
            return

        index = self.trajectory_combo.currentIndex()
        coordinate = self.coordinate_combo.currentText()
        column = self._run["variables"].index(coordinate)
        solution = self._run["solutions"][index]
        spec = self._run["trajectory_specs"][index]
        dt = (spec["t_max"] - self._run["t_min"]) / spec["n"]

        self.signal = prepare_signal(
            solution[:, column], dt=dt, t0=self._run["t_min"] + dt
        )

        self.curve.setData(self.signal.times, self.signal.values)
        self.trace.setLabel("left", coordinate)
        self.trace.enableAutoRange()
        self.info_label.setText(
            f"{self.signal.values.size:,} samples | dt = {dt:.6g} |"
            f"Rate = {1.0 / dt:.6g} samples/times unit\n"
            f"Time: {self.signal.times[0]:.6g} to "
            f"{self.signal.times[-1]:.6g}"
        )

        self.apply_theme()

    def apply_theme(self):
        colours = plot_colours()
        self.trace.setBackground(colours["plot_background"])
        self.trace.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])

        pen = colours["plot_pen"]
        if self._run is not None:
            index = self.trajectory_combo.currentIndex()
            pen = self._run["colours"][index] or pen

        self.curve.setPen(pg.mkPen(pen))
