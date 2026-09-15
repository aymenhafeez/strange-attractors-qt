from pyqtgraph.dockarea.Container import TContainer
from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.Qt import QtCore


class AppDock(Dock):
    container_changed = QtCore.pyqtSignal()
    activated = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hStyle = """
            Dock > QWidget {
                border: none;
            }
        """
        self.vStyle = """
            Dock > QWidget {
                border: none;
            }
        """
        self.nStyle = """
            Dock > QWidget {
                border: none;
            }
        """
        self.updateStyle()

        self.label.sigClicked.connect(lambda _label, _event: self.activated.emit())

    def containerChanged(self, c):
        # c is a container object
        super().containerChanged(c)
        self.container_changed.emit()

    def raiseDock(self):
        container = self.container()
        if isinstance(container, TContainer):
            container.raiseDock(self)

        self.activated.emit()


class AppDockArea(DockArea):
    def addDock(self, dock=None, position="bottom", relativeTo=None, **kwargs):
        sizes = []
        if position in {"above", "below"}:
            containers, _ = self.findAll()
            sizes = [
                (container, container.sizes())
                for container in containers
                if container.type() in {"horizontal", "vertical"}
                and any(container.sizes())
            ]

        result = super().addDock(dock, position, relativeTo, **kwargs)

        for container, previous_sizes in sizes:
            container.setSizes(previous_sizes)

        return result
