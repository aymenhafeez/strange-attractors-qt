from pyqtgraph.Qt import QtCore

from .docking import AppDock


class LegacyViewHost(QtCore.QObject):
    activated = QtCore.pyqtSignal(object)
    closed = QtCore.pyqtSignal(object)

    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self._registered = set()

    def register(self, dock):
        if dock in self._registered:
            return

        self._registered.add(dock)
        dock.activated.connect(lambda dock=dock: self.activated.emit(dock))
        dock.sigClosed.connect(lambda closed: self.closed.emit(closed))

    def create(self, view_id, title, widget, *, relative_to, closable=True):
        dock = AppDock(title, size=(10, 6), closable=closable)
        dock.addWidget(widget)
        self.register(dock)
        self.area.addDock(dock, position="above", relativeTo=relative_to)

        return dock

    def show(self, dock):
        dock.raiseDock()

    def rename(self, dock, title):
        dock.setTitle(title)

    def close(self, dock):
        dock.close()

    def remove(self, dock):
        self._registered.discard(dock)
        dock.label.deleteLater()
        dock.deleteLater()
