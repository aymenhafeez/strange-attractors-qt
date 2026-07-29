from pyqtgraph.dockarea.Dock import Dock
from pyqtgraph.dockarea.DockArea import DockArea
from pyqtgraph.dockarea.DockDrop import DockDrop
from pyqtgraph.Qt import QtCore

from .style import DOCK_HORIZONTAL, DOCK_NO_TITLE, DOCK_VERTICAL


class AreaBoundDockDrop(DockDrop):
    def _source_matches_target_area(self, event):
        source = event.source()
        if not (hasattr(source, "implements") and source.implements("dock")):
            return False
        return getattr(source, "area", None) is getattr(self.dndWidget, "area", None)

    def dragEnterEvent(self, event):
        if self._source_matches_target_area(event):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._source_matches_target_area(event):
            super().dragMoveEvent(event)
        else:
            self.dropArea = None
            self.overlay.setDropArea(None)
            event.ignore()

    def dropEvent(self, event):
        if self._source_matches_target_area(event):
            super().dropEvent(event)
        else:
            self.dropArea = None
            self.overlay.setDropArea(None)
            event.ignore()


class AreaBoundDock(Dock):
    container_changed = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hStyle = DOCK_HORIZONTAL
        self.vStyle = DOCK_VERTICAL
        self.nStyle = DOCK_NO_TITLE
        self.updateStyle()
        self.dockdrop.overlay.setParent(None)
        self.dockdrop.overlay.deleteLater()
        self.dockdrop = AreaBoundDockDrop(self)
        self.dockdrop.raiseOverlay()

    def containerChanged(self, container):
        super().containerChanged(container)
        self.container_changed.emit()


class AreaBoundDockArea(DockArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dockdrop.overlay.setParent(None)
        self.dockdrop.overlay.deleteLater()
        self.dockdrop = AreaBoundDockDrop(self)
        self.dockdrop.removeAllowedArea("center")
        self.dockdrop.raiseOverlay()
