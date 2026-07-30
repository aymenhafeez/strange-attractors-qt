"""Adapted from the Rich Jupyter Console pyqtgraph example"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .docking import AreaBoundDock as Dock
from .docking import AreaBoundDockArea as DockArea
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
    def __init__(self, plot_widget):
        self._plot_widget = plot_widget
        self._manager = None
        self._legend = None

    def __repr__(self):
        return "ConsolePlot()"

    def set_manager(self, manager):
        self._manager = manager

    def __call__(self, x, y, **kwargs):
        return self.line(x, y, **kwargs)

    def clear(self):
        self._plot_widget.clear()
        self._legend = None

    def auto_range(self):
        self._plot_widget.autoRange()

    def set_labels(self, *, bottom=None, left=None):
        if bottom is not None:
            self._plot_widget.setLabel("bottom", bottom)
        if left is not None:
            self._plot_widget.setLabel("left", left)

    def has_item(self, item):
        return item in self._plot_widget.listDataItems()

    def line(
        self,
        x,
        y,
        *,
        clear=True,
        bottom=None,
        left=None,
        plot_widget=None,
        **kwargs,
    ):
        if plot_widget is not None:
            target = self._plot_target(plot_widget)
            return target.line(
                x,
                y,
                clear=clear,
                bottom=bottom,
                left=left,
                **kwargs,
            )

        if clear:
            self.clear()
        if kwargs.get("name"):
            self.ensure_legend()
        item = self._plot_widget.plot(x, y, **kwargs)
        self.set_labels(bottom=bottom, left=left)
        return item

    def scatter(
        self,
        x,
        y,
        *,
        clear=True,
        bottom=None,
        left=None,
        plot_widget=None,
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
            clear=clear,
            bottom=bottom,
            left=left,
            plot_widget=plot_widget,
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


class JupyterConsolePanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, namespace_factory, script_dir=None, parent=None):
        super().__init__(parent)
        self._namespace_factory = namespace_factory
        self._console = None
        self._script_dir = script_dir
        self.setMinimumHeight(180)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.dock_area = DockArea()
        self._layout.addWidget(self.dock_area)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.plot_widget.setLabel("bottom", "x")
        self.plot_widget.setLabel("left", "y")
        self.plot = ConsolePlot(self.plot_widget)
        self.plot_dock = Dock("Plot", size=(10, 6))
        self.plot_dock.addWidget(self.plot_widget)
        self.dock_area.addDock(self.plot_dock)

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
