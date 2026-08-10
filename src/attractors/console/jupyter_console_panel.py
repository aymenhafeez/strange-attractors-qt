"""Adapted from the Rich Jupyter Console pyqtgraph example"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.docking import AreaBoundDock as Dock
from ..ui.docking import AreaBoundDockArea as DockArea
from ..ui.style import CONSOLE_PLOT_PARAMS, CONSOLE_PLOT_WIDGET
from .explorer import PlotExplorer
from .script_panel import ScriptPanel

try:
    from qtconsole import inprocess
except (ImportError, NameError) as exc:
    inprocess = None
    CONSOLE_IMPORT_ERROR = exc
else:
    CONSOLE_IMPORT_ERROR = None


_BaseJupyterConsole = (
    inprocess.QtInProcessRichJupyterWidget if inprocess else QtWidgets.QWidget
)
LEGEND_OFFSET = (-12, 12)
LEGEND_BRUSH = (18, 22, 28, 220)
LEGEND_PEN = (210, 220, 230, 180)
LEGEND_TEXT = (245, 248, 252)
LEGEND_TEXT_SIZE = "9pt"
PLOT_MODE_REPLACE = "replace"
PLOT_MODE_OVERLAY = "overlay"


def _build_console_plot_widget():
    plot_widget = pg.PlotWidget()
    plot_widget.setObjectName("ConsolePlotWidget")
    # plot_widget.setStyleSheet(CONSOLE_PLOT_WIDGET)
    plot_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    plot_widget.showGrid(x=True, y=True, alpha=0.25)
    plot_widget.setLabel("bottom", "x")
    plot_widget.setLabel("left", "y")

    return plot_widget


class _RichJupyterConsole(_BaseJupyterConsole):
    def __init__(self, namespace, script_dir=None, parent=None):
        super().__init__(parent)
        self.kernel_manager = inprocess.QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.kernel_manager.kernel.shell.push(namespace)

        if script_dir is not None:
            self.kernel_manager.kernel.shell.run_line_magic("cd", str(script_dir))
        self.set_default_style("linux")

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()

    def push_namespace(self, namespace):
        self.kernel_manager.kernel.shell.push(namespace)


class ConsolePlot:
    def __init__(self, plot_widget, status_callback=None):
        self._plot_widget = plot_widget
        self._manager = None
        self._legend = None
        self._zoom = None

        self.host = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self._plot_widget)

        self.param_widget = QtWidgets.QFrame()
        self.param_widget.setObjectName("ConsolePlotParams")
        self.param_layout = QtWidgets.QVBoxLayout(self.param_widget)
        self.param_layout.setContentsMargins(6, 5, 6, 6)
        self.param_layout.setSpacing(4)
        self.param_widget.setVisible(False)
        self.param_widget.setStyleSheet(CONSOLE_PLOT_PARAMS)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(4)

        # self.param_title = QtWidgets.QLabel("Explore")
        # self.param_title.setObjectName("ConsolePlotParamTitle")

        clear_traces = QtWidgets.QToolButton()
        clear_traces.setText("Traces")
        clear_traces.setToolTip("Clear reactive traces")
        clear_traces.clicked.connect(lambda: self.explore.clear_traces())

        clear_sliders = QtWidgets.QToolButton()
        clear_sliders.setText("Sliders")
        clear_sliders.setToolTip("Clear sliders")
        clear_sliders.clicked.connect(lambda: self.explore.clear_sliders())

        # header_layout.addWidget(self.param_title)
        header_layout.addStretch(1)
        header_layout.addWidget(clear_traces)
        header_layout.addWidget(clear_sliders)

        self.param_controls = QtWidgets.QFrame()
        self.param_controls.setObjectName("ConsolePlotParamControls")
        self.param_controls_layout = QtWidgets.QVBoxLayout(self.param_controls)
        self.param_controls_layout.setContentsMargins(5, 5, 5, 5)
        self.param_controls_layout.setSpacing(3)

        self.param_layout.addWidget(header)
        self.param_layout.addWidget(self.param_controls)

        self.layout.addWidget(self.param_widget)

        self.explore = PlotExplorer(
            self,
            self.param_widget,
            self.param_controls_layout,
            status_callback=status_callback,
            parent=self.host,
        )

    def __repr__(self):
        return "ConsolePlot()"

    def __call__(self, x, y, **kwargs):
        return self.line(x, y, **kwargs)

    def clear(self):
        self._plot_widget.clear()
        if hasattr(self, "explore"):
            self.explore.clear_traces()

        if self._zoom is not None:
            self._zoom.clear()
            self._plot_widget.addItem(self._zoom.region, ignoreBounds=True)

        self._legend = None

    def zoom_region(self, enabled=True):
        if enabled and self._zoom is None:
            self.layout.removeWidget(self._plot_widget)
            self._zoom = ConsolePlotZoom(self._plot_widget)

            for item in self._plot_widget.listDataItems():
                self._zoom.add_item(item)

            self.layout.addWidget(self._zoom)

        elif not enabled and self._zoom is not None:
            self.layout.removeWidget(self._zoom)
            self._zoom.setParent(None)
            self._zoom = None
            self.layout.addWidget(self._plot_widget)

        return self.host

    def auto_range(self):
        if self._zoom is not None:
            self._zoom.auto_range()
        else:
            self._plot_widget.autoRange()

    def set_labels(self, *, bottom=None, left=None):
        if bottom is not None:
            self._plot_widget.setLabel("bottom", bottom)
        if left is not None:
            self._plot_widget.setLabel("left", left)
        if self._zoom is not None:
            self._zoom.set_labels(bottom=bottom, left=left)

    def has_item(self, item):
        return item in self._plot_widget.listDataItems()

    def line(
        self,
        x,
        y,
        *,
        bottom=None,
        left=None,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        zoom_region=False,
        **kwargs,
    ):
        if plot is not None:
            target = self._plot_target(plot)
            return target.line(
                x,
                y,
                mode=mode,
                bottom=bottom,
                left=left,
                zoom_region=zoom_region,
                **kwargs,
            )

        if self._clear_for_mode(mode):
            self.clear()
        if zoom_region:
            self.zoom_region(True)
        elif mode == PLOT_MODE_REPLACE:
            self.zoom_region(False)
        if kwargs.get("name"):
            self.ensure_legend()
        item = self._plot_widget.plot(x, y, **kwargs)

        if self._zoom is not None:
            self._zoom.add_item(item)

        self.set_labels(bottom=bottom, left=left)

        return item

    def scatter(
        self,
        x,
        y,
        *,
        bottom=None,
        left=None,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        zoom_region=False,
        symbol="o",
        symbol_size=None,
        **kwargs,
    ):
        kwargs.setdefault("pen", None)
        kwargs.setdefault("symbol", symbol)
        if symbol_size is not None:
            kwargs.setdefault("symbolSize", symbol_size)
        return self.line(
            x,
            y,
            bottom=bottom,
            left=left,
            plot=plot,
            mode=mode,
            zoom_region=zoom_region,
            **kwargs,
        )

    def ensure_legend(self):
        if self._legend is None:
            self._legend = self._plot_widget.addLegend(
                offset=LEGEND_OFFSET,
                brush=LEGEND_BRUSH,
                pen=LEGEND_PEN,
                labelTextColor=LEGEND_TEXT,
                labelTextSize=LEGEND_TEXT_SIZE,
            )
        return self._legend

    def _plot_target(self, plot_widget):
        if isinstance(plot_widget, str):
            if self._manager is None:
                raise ValueError("Named plot targets require a plot manager")
            try:
                return self._manager.get(plot_widget)
            except KeyError:
                return self._manager.new(plot_widget)

        return plot_widget

    def _clear_for_mode(self, mode):
        mode = str(mode).strip().lower()
        if mode == PLOT_MODE_REPLACE:
            return True
        if mode == PLOT_MODE_OVERLAY:
            return False
        raise ValueError("Plot mode must be 'replace' or 'overlay'")


class ConsolePlotManager(QtCore.QObject):
    plots_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    plot_removed = QtCore.pyqtSignal(str, object)
    plot_cleared = QtCore.pyqtSignal(str, object)

    def __init__(
        self, dock_area, default_name, default_plot, default_dock, status_callback=None
    ):
        super().__init__(dock_area)
        self._dock_area = dock_area
        self._plots = {default_name: default_plot}
        self._docks = {default_name: default_dock}
        self._current_name = default_name
        self._default_name = default_name
        self._status_callback = status_callback
        default_plot.explore.status_callback = status_callback
        default_plot._manager = self

    def __repr__(self):
        return f"ConsolePlotManager(current={self._current_name!r})"

    def __call__(self, x, y, **kwargs):
        return self.current(x, y, **kwargs)

    @property
    def current(self):
        return self._plots[self._current_name]

    @property
    def current_name(self):
        return self._current_name

    def names(self):
        return list(self._plots)

    def set_status_callback(self, callback):
        self._status_callback = callback
        for plot in self._plots.values():
            plot.explore.status_callback = callback

    def get(self, name, *, activate=True):
        key = self._plot_name(name)
        try:
            plot = self._plots[key]
        except KeyError as exc:
            raise KeyError(f"No console plot named {key!r}") from exc
        if activate:
            self._set_current_name(key)
            dock = self._docks[key]
            self._raise_dock(dock)

        return plot

    def rename(self, old_name, new_name):
        old_key = self._plot_name(old_name)
        new_key = self._plot_name(new_name)
        if old_key not in self._plots:
            raise KeyError(f"No console plot named {old_key!r}")
        if new_key != old_key and new_key in self._plots:
            raise ValueError(f"Console plot {new_key!r} already exists")

        if new_key == old_key:
            self._set_current_name(new_key)
            return self._plots[new_key]

        plot = self._plots.pop(old_key)
        dock = self._docks.pop(old_key)
        self._plots[new_key] = plot
        self._docks[new_key] = dock
        if old_key == self._default_name:
            self._default_name = new_key
        if old_key == self._current_name:
            self._current_name = new_key
        dock.setTitle(new_key)
        self.plots_changed.emit()
        self.current_changed.emit(self._current_name)

        return plot

    def _set_current_name(self, key):
        if self._current_name == key:
            return

        self._current_name = key
        self.current_changed.emit(key)

    def new(self, name=None, *, activate=True):
        key = self._next_name() if name is None else self._plot_name(name)
        if key in self._plots:
            return self.get(key, activate=activate)

        plot_widget = _build_console_plot_widget()
        plot = ConsolePlot(plot_widget, status_callback=self._status_callback)
        # i can't remember why this is needed
        plot._manager = self
        dock = Dock(key, size=(10, 6), closable=True)
        dock.addWidget(plot.host)
        dock.sigClosed.connect(lambda _dock, plot_name=key: self._forget(plot_name))
        self._dock_area.addDock(
            dock,
            position="above",
            relativeTo=self._docks[self._default_name],
        )
        self._plots[key] = plot
        self._docks[key] = dock
        if activate:
            self._set_current_name(key)
            dock.raiseDock()
        self.plots_changed.emit()

        return plot

    def close(self, name=None):
        key = self._current_name if name is None else self._plot_name(name)
        if key == self._default_name:
            plot = self._plots[key]
            plot.clear()
            self.plot_cleared.emit(key, plot)
            self._set_current_name(key)

            return

        dock = self._docks.get(key)
        if dock is not None and dock.container() is not None:
            # closing the dock triggers sigClosed, which calls _forget itself
            dock.close()
        else:
            self._forget(key)

    def clear_all(self):
        for name, plot in self._plots.items():
            plot.clear()
            self.plot_cleared.emit(name, plot)

    def clear(self):
        plot = self.current
        plot.clear()
        self.plot_cleared.emit(self._current_name, plot)

    def auto_range(self):
        self.current.auto_range()

    def set_labels(self, **kwargs):
        self.current.set_labels(**kwargs)

    def line(self, *args, zoom_region=False, **kwargs):
        return self.current.line(*args, zoom_region=zoom_region, **kwargs)

    def scatter(self, *args, zoom_region=False, **kwargs):
        return self.current.scatter(*args, zoom_region=zoom_region, **kwargs)

    def _raise_dock(self, dock):
        container = dock.container()
        raise_dock = getattr(container, "raiseDock", None)
        if raise_dock is not None:
            raise_dock(dock)

    def _forget(self, name):
        if name == self._default_name:
            return
        if name not in self._plots:
            return

        plot = self._plots.pop(name)
        self._docks.pop(name, None)
        if self._current_name == name:
            self._set_current_name(self._default_name)

        self.plot_removed.emit(name, plot)
        self.plots_changed.emit()

    def _next_name(self):
        index = 2
        while True:
            name = f"Plot {index}"
            if name not in self._plots:
                return name
            index += 1

    def _plot_name(self, name):
        key = str(name).strip()
        if not key:
            raise ValueError("Plot name cannot be empty")
        return key


class JupyterConsolePanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, namespace_factory, script_dir=None, parent=None):
        super().__init__(parent)
        self._namespace_factory = namespace_factory
        self._console = None
        self._script_dir = script_dir
        self._explore_status_callback = None
        self.setMinimumHeight(180)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.dock_area = DockArea()
        self._layout.addWidget(self.dock_area)

        self.plot_widget = _build_console_plot_widget()
        self.plot = ConsolePlot(
            self.plot_widget, status_callback=self._explore_status_callback
        )
        self.plot_dock = Dock("Plot", size=(10, 6))
        self.plot_dock.addWidget(self.plot.host)
        self.dock_area.addDock(self.plot_dock)
        self.plots = ConsolePlotManager(
            self.dock_area,
            "Plot",
            self.plot,
            self.plot_dock,
            status_callback=self._explore_status_callback,
        )

        # self.explorer_params = QtWidgets.QWidget()
        # self.explorer_params_layout = QtWidgets.QVBoxLayout(self.explorer_params)
        # self.explorer_params_layout.setContentsMargins(0, 0, 0, 0)
        # self.explorer_params_layout.setSpacing(0)
        # self.explorer_params_layout.addStretch()
        # self.explorer = ConsoleExplorer(self.plots)

        # self.explorer_params_dock = Dock("Parameters", size=(10, 3), closable=False)
        # self.explorer_params_dock.addWidget(self.explorer_params)
        # self.dock_area.addDock(
        #     self.explorer_params_dock, position="bottom", relativeTo=self.plot_dock
        # )

        self.set_explore_visible(False)

        self._console_host = QtWidgets.QWidget()
        self._console_layout = QtWidgets.QVBoxLayout(self._console_host)
        self._console_layout.setContentsMargins(0, 0, 0, 0)
        self._console_layout.setSpacing(0)

        self.script_panel = ScriptPanel(self._script_dir)
        self.script_panel.run_requested.connect(self.run_script_text)

        self.script_dock = Dock("Script", size=(10, 8), closable=False)
        self.console_dock = Dock("Console", size=(10, 8))
        self.script_dock.addWidget(self.script_panel)
        self.console_dock.addWidget(self._console_host)

        self.dock_area.addDock(
            self.script_dock,
            position="bottom",
            relativeTo=self.plot_dock,
        )
        self.dock_area.addDock(
            self.console_dock,
            position="above",
            relativeTo=self.script_dock,
        )

        if CONSOLE_IMPORT_ERROR is not None:
            message = QtWidgets.QLabel(
                "Install qtconsole and ipykernel to enable the embedded Jupyter console."
            )
            message.setWordWrap(True)
            self._console_layout.addWidget(message)

    def ensure_console(self):
        if self._console is not None or CONSOLE_IMPORT_ERROR is not None:
            return

        self._console = _RichJupyterConsole(
            self._namespace_factory(), script_dir=self._script_dir, parent=self
        )
        self._console_layout.addWidget(self._console)

    def focus_console(self):
        if self._console is not None:
            self._console.setFocus()
        else:
            self.plot_widget.setFocus()

    def shutdown_kernel(self):
        if self._console is not None:
            self._console.shutdown_kernel()

    def run_script_text(self, code):
        self.ensure_console()
        if self._console is None:
            return

        self._console.push_namespace(self._namespace_factory())
        self._console.execute(code)

    def set_explore_visible(self, visible):
        for plot in self.plots._plots.values():
            plot.param_widget.setVisible(bool(visible) and bool(plot.explore.params()))

    def apply_explore_layout(self):
        self.set_explore_visible(True)
        self.dock_area.moveDock(self.script_dock, "left", self.plot_dock)
        self.dock_area.moveDock(self.console_dock, "bottom", self.script_dock)
        # self.dock_area.moveDock(
        #     self.explorer_params_dock,
        #     "bottom",
        #     self.console_dock,
        # )

    def set_explore_status_callback(self, callback):
        self._explore_status_callback = callback
        self.plots.set_status_callback(callback)


class ConsolePlotZoom(QtWidgets.QWidget):
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.zoom_widget = pg.PlotWidget()
        self.region = pg.LinearRegionItem()
        self.items = {}
        self.x_bounds = None
        self.updating = False

        self.zoom_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.zoom_widget.showGrid(x=True, y=True, alpha=0.25)
        self.zoom_widget.setLabel("bottom", "x")
        self.zoom_widget.setLabel("left", "y")

        self.region.setZValue(10)
        self.plot_widget.addItem(self.region, ignoreBounds=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.zoom_widget, 2)
        layout.addWidget(self.plot_widget, 1)

        self.region.sigRegionChanged.connect(self.region_changed)
        self.zoom_widget.sigXRangeChanged.connect(self.zoom_range_changed)

    def add_item(self, item):
        x, y = item.getData()
        clone = self.zoom_widget.plot(x, y, pen=item.opts.get("pen"))
        self.items[item] = clone

        if x is not None and len(x):
            x_min = float(x[0])
            x_max = float(x[-1])

            if x_max > x_min:
                self.x_bounds = (x_min, x_max)
                self.region.setBounds((x_min, x_max))
                self.region.setRegion((x_min, x_min + (x_max - x_min) * 0.1))

        item.sigPlotChanged.connect(lambda: self.item_changed(item))

    def clear(self):
        self.items.clear()
        self.x_bounds = None
        self.zoom_widget.clear()

    def auto_range(self):
        self.plot_widget.autoRange()
        self.zoom_widget.autoRange()

    def set_labels(self, *, bottom=None, left=None):
        if bottom is not None:
            self.zoom_widget.setLabel("bottom", bottom)
        if left is not None:
            self.zoom_widget.setLabel("left", left)

    def item_changed(self, item):
        clone = self.items.get(item)
        if clone is None:
            return

        x, y = item.getData()
        clone.setData(x, y)
        if x is not None and len(x):
            x_min = float(x[0])
            x_max = float(x[-1])

            if x_max > x_min and self.x_bounds != (x_min, x_max):
                self.x_bounds = (x_min, x_max)
                region_min, region_max = self.region.getRegion()
                self.region.setBounds((x_min, x_max))
                # check if the old region is outside the new range and reset it to the first 10% of the new range
                if region_max <= x_min or region_min >= x_max:
                    self.region.setRegion((x_min, x_min + (x_max - x_min) * 0.1))
                else:
                    # keep the old region if it overlaps with the new range
                    self.region.setRegion(
                        (max(region_min, x_min), min(region_max, x_max))
                    )

    def region_changed(self):
        if self.updating:
            return

        self.updating = True
        x_min, x_max = self.region.getRegion()
        self.zoom_widget.setXRange(x_min, x_max, padding=0)
        self.updating = False

    def zoom_range_changed(self, *_args):
        if self.updating:
            return

        self.updating = True
        self.region.setRegion(self.zoom_widget.getViewBox().viewRange()[0])
        self.updating = False
