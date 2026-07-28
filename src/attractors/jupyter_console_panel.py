"""Adapted from the Rich Jupyter Console pyqtgraph example"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .docking import AreaBoundDock as Dock
from .docking import AreaBoundDockArea as DockArea

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
    def __init__(self, namespace, parent=None):
        super().__init__(parent)
        self.kernel_manager = inprocess.QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.kernel_manager.kernel.shell.push(namespace)
        self.set_default_style("linux")

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


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
class JupyterConsolePanel(QtWidgets.QWidget):
    close_requested = QtCore.pyqtSignal()

    def __init__(self, namespace_factory, parent=None):
        super().__init__(parent)
        self._namespace_factory = namespace_factory
        self._console = None
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
        self.console_dock = Dock("Console", size=(10, 8))
        self.console_dock.addWidget(self._console_host)
        self.dock_area.addDock(
            self.console_dock,
            position="bottom",
            relativeTo=self.plot_dock,
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

        self._console = _RichJupyterConsole(self._namespace_factory(), self)
        self._console_layout.addWidget(self._console)

    def focus_console(self):
        if self._console is not None:
            self._console.setFocus()
        else:
            self.plot_widget.setFocus()

    def shutdown_kernel(self):
        if self._console is not None:
            self._console.shutdown_kernel()
