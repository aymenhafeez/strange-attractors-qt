from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.dockarea.DockDrop import DockDrop
from pyqtgraph.Qt import QtCore


class AreaBoundDockDrop(DockDrop):
    def _source_matches_target_area(self, event):
        source = event.source()
        if not (hasattr(source, "implements") and source.implements("dock")):
            return False
        return getattr(source, "area", None) is getattr(self.dndWidget, "area", None)

    def dragEnterEvent(self, ev):
        if self._source_matches_target_area(ev):
            ev.accept()
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if self._source_matches_target_area(ev):
            super().dragMoveEvent(ev)
        else:
            self.dropArea = None
            self.overlay.setDropArea(None)
            ev.ignore()

    def dropEvent(self, ev):
        if self._source_matches_target_area(ev):
            super().dropEvent(ev)
        else:
            self.dropArea = None
            self.overlay.setDropArea(None)
            ev.ignore()


class AreaBoundDock(Dock):
    container_changed = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dockdrop.overlay.setParent(None)
        self.dockdrop.overlay.deleteLater()
        self.dockdrop = AreaBoundDockDrop(self)
        self.dockdrop.raiseOverlay()

    def containerChanged(self, c):
        # c is a container object
        super().containerChanged(c)
        self.container_changed.emit()


class AreaBoundDockArea(DockArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dockdrop.overlay.setParent(None)
        self.dockdrop.overlay.deleteLater()
        self.dockdrop = AreaBoundDockDrop(self)
        self.dockdrop.removeAllowedArea("center")
        self.dockdrop.raiseOverlay()
