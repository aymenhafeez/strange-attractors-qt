import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.docking import AppDock as Dock
from ..ui.docking import AppDockArea as DockArea
from ..ui.style import CONSOLE_PLOT_PARAMS, plot_colours
from .explorer import PlotExplorer
from .script_panel import ScriptPanel
from .table import ConsoleTable, ConsoleTableManager
from .view3d import ConsoleView3D, ConsoleView3DManager

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
    plot_widget.setBackground(plot_colours()["plot_background"])
    plot_widget.setLabel("bottom", "x")
    plot_widget.setLabel("left", "y")

    return plot_widget


# Adapted from the Rich Jupyter Console pyqtgraph example
class _RichJupyterConsole(_BaseJupyterConsole):
    def __init__(self, namespace, script_dir=None, parent=None):
        super().__init__(parent)
        self.kernel_manager = inprocess.QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_client = self.kernel_manager.client()
        self.kernel_manager.kernel.shell.banner2 = (
            "Use system.help() to see available system commands\n"
            "Use workspace.help() to see available workspace commands"
        )
        self.kernel_client.start_channels()
        self.kernel_manager.kernel.shell.push(namespace)

        if script_dir is not None:
            self.kernel_manager.kernel.shell.run_line_magic("cd", str(script_dir))

        self.set_default_style(plot_colours()["console_theme"])

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

        self._crosshair = ConsolePlotCrossHair(self._plot_widget, parent=self.host)

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

        # header = QtWidgets.QWidget()
        # header_layout = QtWidgets.QHBoxLayout(header)
        # header_layout.setContentsMargins(0, 0, 0, 2)
        # header_layout.setSpacing(4)

        # self.param_title = QtWidgets.QLabel("Explore")
        # self.param_title.setObjectName("ConsolePlotParamTitle")

        self.trace_menu = QtWidgets.QMenu(self.param_widget)
        # self.param_title = QtWidgets.QLabel("Parameters")
        # self.param_title.setObjectName("ConsolePlotParamTitle")

        # header_layout.addWidget(self.param_title)
        # header_layout.addStretch(1)

        self.param_controls = QtWidgets.QFrame()
        self.param_controls.setObjectName("ConsolePlotParamControls")
        self.param_controls_layout = QtWidgets.QVBoxLayout(self.param_controls)
        self.param_controls_layout.setContentsMargins(5, 5, 5, 5)
        self.param_controls_layout.setSpacing(3)

        # self.param_layout.addWidget(header)
        self.param_layout.addWidget(self.param_controls)

        self.layout.addWidget(self.param_widget)

        self.explore = PlotExplorer(
            self,
            self.param_widget,
            self.param_controls_layout,
            self.trace_menu,
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

    def grid_visible(self):
        plot_item = self._plot_widget.getPlotItem()
        return (
            plot_item.ctrl.xGridCheck.isChecked()
            and plot_item.ctrl.yGridCheck.isChecked()
        )

    def set_grid_visible(self, visible):
        self._plot_widget.showGrid(
            x=visible, y=visible, alpha=plot_colours()["plot_grid_alpha"]
        )

    def crosshair_visible(self):
        return self._crosshair.visible()

    def set_crosshair_visible(self, visible):
        self._crosshair.set_visible(visible)

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
        width=1.0,
        zoom_region=False,
        **kwargs,
    ):
        kwargs.setdefault("pen", plot_colours()["scatter_brush"])
        if plot is not None:
            target = self._plot_target(plot)
            return target.line(
                x,
                y,
                mode=mode,
                bottom=bottom,
                left=left,
                width=width,
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
        kwargs.setdefault("pen", plot_colours()["scatter_brush"])
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

    def apply_theme(self):
        colours = plot_colours()

        plot_item = self._plot_widget.getPlotItem()
        x_grid = plot_item.ctrl.xGridCheck.isChecked()
        y_grid = plot_item.ctrl.yGridCheck.isChecked()

        self._plot_widget.setBackground(colours["plot_background"])
        self._plot_widget.showGrid(x=x_grid, y=y_grid, alpha=colours["plot_grid_alpha"])
        self.param_widget.setStyleSheet(CONSOLE_PLOT_PARAMS)

        if self._zoom is not None:
            self._zoom.apply_theme()

        self._crosshair.apply_theme()


class ConsolePlotManager(QtCore.QObject):
    plots_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    plot_removed = QtCore.pyqtSignal(str, object)
    plot_cleared = QtCore.pyqtSignal(str, object)

    def __init__(
        self,
        dock_area,
        default_name,
        default_plot,
        default_dock,
        status_callback=None,
        active_callback=None,
    ):
        super().__init__(dock_area)
        self._dock_area = dock_area
        self._plots = {default_name: default_plot}
        self._docks = {default_name: default_dock}
        self._current_name = default_name
        self._default_name = default_name
        self._status_callback = status_callback
        self._active_callback = active_callback
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
            self._mark_active()
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

        self._mark_active()

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

    def activate(self, name):
        key = self._plot_name(name)
        if key not in self._plots:
            return

        self._set_current_name(key)
        self._mark_active()

    def _mark_active(self):
        if self._active_callback is not None:
            self._active_callback("plot")

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

        dock.activated.connect(lambda plot_name=key: self.activate(plot_name))
        dock.sigClosed.connect(self._forget_dock)

        self._dock_area.addDock(
            dock,
            position="above",
            relativeTo=self._docks[self._default_name],
        )
        self._plots[key] = plot
        self._docks[key] = dock

        if activate:
            self._mark_active()
            self._set_current_name(key)
            dock.raiseDock()
        self.plots_changed.emit()

        return plot

    def _forget_dock(self, dock):
        for name, known_dock in self._docks.items():
            if known_dock is dock:
                self._forget(name)
                return

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

    def grid_visible(self):
        return self.current.grid_visible()

    def set_grid_visible(self, visible):
        return self.current.set_grid_visible(visible)

    def crosshair_visible(self):
        return self.current.crosshair_visible()

    def set_crosshair_visible(self, visible):
        return self.current.set_crosshair_visible(visible)

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

    def apply_theme(self):
        for plot in self._plots.values():
            plot.apply_theme()


class JupyterConsolePanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()
    active_view_changed = QtCore.pyqtSignal()

    def __init__(self, namespace_factory, script_dir=None, parent=None):
        super().__init__(parent)
        self._namespace_factory = namespace_factory
        self._console = None
        self._script_dir = script_dir
        self._explore_status_callback = None
        self._active_view = "plot"
        self.setMinimumHeight(180)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.dock_area = DockArea()
        self._layout.addWidget(self.dock_area)

        self.view3d = ConsoleView3D(status_callback=self._explore_status_callback)
        self.view3d_dock = Dock("3D View", size=(10, 6), closable=False)
        self.view3d_dock.addWidget(self.view3d.host)
        self.dock_area.addDock(self.view3d_dock)

        self.views3d = ConsoleView3DManager(
            self.dock_area,
            "3D View",
            self.view3d,
            self.view3d_dock,
            status_callback=self._explore_status_callback,
            active_callback=self.set_active_view,
        )

        self.view3d_dock.activated.connect(lambda: self.views3d.activate("3D View"))

        self.plot_widget = _build_console_plot_widget()
        self.plot = ConsolePlot(
            self.plot_widget, status_callback=self._explore_status_callback
        )
        self.plot_dock = Dock("Plot", size=(10, 6))
        self.plot_dock.addWidget(self.plot.host)
        self.dock_area.addDock(
            self.plot_dock, position="above", relativeTo=self.view3d_dock
        )
        self.plots = ConsolePlotManager(
            self.dock_area,
            "Plot",
            self.plot,
            self.plot_dock,
            status_callback=self._explore_status_callback,
            active_callback=self.set_active_view,
        )

        self.table = ConsoleTable()
        self.table_dock = Dock("Table", size=(10, 6), closable=False)
        self.table_dock.addWidget(self.table.host)
        self.dock_area.addDock(
            self.table_dock, position="above", relativeTo=self.plot_dock
        )
        self.tables = ConsoleTableManager(
            self.dock_area,
            "Table",
            self.table,
            self.table_dock,
            status_callback=self._explore_status_callback,
        )

        self.plot_dock.activated.connect(lambda: self.plots.activate("Plot"))
        self.table_dock.activated.connect(lambda: self.tables.activate("Table"))

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

    def active_view(self):
        if self._active_view == "view3d":
            return self.views3d.current
        return self.plots.current

    def active_explorer(self):
        return self.active_view().explore

    def workspace_view_items(self):
        items = []

        for name in self.plots.names():
            items.append(
                {
                    "kind": "plot",
                    "name": name,
                    "label": name,
                }
            )

        for name in self.views3d.names():
            items.append(
                {
                    "kind": "view3d",
                    "name": name,
                    "label": f"3D: {name}",
                }
            )

        return items

    def active_view_key(self):
        if self._active_view == "view3d":
            return ("view3d", self.views3d.current_name)

        return ("plot", self.plots.current_name)

    def set_active_workspace_view(self, kind, name, *, activate=True):
        key = str(kind).strip().lower()
        if key == "view3d":
            return self.views3d.get(name, activate=activate)
        if key == "plot":
            return self.plots.get(name, activate=activate)

        raise ValueError("Workspace view kind must be 'plot' or 'view3d'")

    def set_active_view(self, kind):
        key = str(kind).strip().lower()
        if key not in {"plot", "view3d"}:
            raise ValueError("Active view kind must be 'plot' or 'view3d'")

        if self._active_view == key:
            return

        self._active_view = key
        self.active_view_changed.emit()

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
            plot.param_widget.setVisible(bool(visible) and plot.explore.has_controls())

        for view in self.views3d._views.values():
            view.param_widget.setVisible(bool(visible) and view.explore.has_controls())

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
        self.views3d.set_status_callback(callback)
        self.tables.set_status_callback(callback)

    def apply_theme(self):
        self.plots.apply_theme()
        self.views3d.apply_theme()
        if self._console is not None:
            self._console.set_default_style(plot_colours()["console_theme"])


# https://github.com/pyqtgraph/pyqtgraph/blob/master/pyqtgraph/examples/crosshair.py
class ConsolePlotCrossHair(QtCore.QObject):
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.plot_item = plot_widget.getPlotItem()
        self.view_box = self.plot_item.getViewBox()
        self._mouse_proxy = None
        self._visible = False

        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.label = pg.TextItem(anchor=(0, 1), fill=pg.mkColor(18, 22, 28, 220))

        for item in (self.v_line, self.h_line, self.label):
            item.setZValue(10)
            item.hide()
            self.plot_item.addItem(item, ignoreBounds=True)

        self.apply_theme()

    def _ensure_items_added(self):
        for item in (self.v_line, self.h_line, self.label):
            if item.scene() is None:
                self.plot_item.addItem(item, ignoreBounds=True)

    def visible(self):
        return self._visible

    def set_visible(self, visible):
        visible = bool(visible)
        if self._visible == visible:
            return

        self._visible = visible
        if visible:
            self._ensure_items_added()
            self._mouse_proxy = pg.SignalProxy(
                self.plot_widget.scene().sigMouseMoved,
                rateLimit=60,
                slot=self._mouse_moved,
            )
            return

        if self._mouse_proxy is not None:
            self._mouse_proxy.disconnect()
            self._mouse_proxy = None
        self._hide_items()

    def _mouse_moved(self, ev):
        self._ensure_items_added()
        pos = ev[0]
        if not self.plot_item.sceneBoundingRect().contains(pos):
            self._hide_items()
            return

        point = self.view_box.mapSceneToView(pos)
        x = point.x()
        y = point.y()

        self.v_line.setPos(x)
        self.h_line.setPos(y)
        self.label.setText(f"x={x:.3f}\ny={y:.3f}")
        self.label.setPos(x, y)

        self.v_line.show()
        self.h_line.show()
        self.label.show()

    def _hide_items(self):
        for item in (self.v_line, self.h_line, self.label):
            item.hide()

    def apply_theme(self):
        colour = plot_colours()
        pen = pg.mkPen(colour["crosshair"], width=1)
        self.v_line.setPen(pen)
        self.h_line.setPen(pen)
        self.label.setColor(colour["label_text"])


class ConsolePlotZoom(QtWidgets.QWidget):
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget

        self.zoom_widget = pg.PlotWidget()
        self.zoom_widget.setBackground(plot_colours()["plot_background"])

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
        clone_options = {
            "pen": item.opts.get("pen"),
            "symbol": item.opts.get("symbol"),
            "symbolSize": item.opts.get("symbolSize"),
            "symbolPen": item.opts.get("symbolPen"),
            "symbolBrush": item.opts.get("symbolBrush"),
        }
        clone = self.zoom_widget.plot(x, y, **clone_options)
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

    def apply_theme(self):
        colours = plot_colours()

        self.zoom_widget.setBackground(colours["plot_background"])
        self.zoom_widget.showGrid(x=True, y=True, alpha=colours["plot_grid_alpha"])
