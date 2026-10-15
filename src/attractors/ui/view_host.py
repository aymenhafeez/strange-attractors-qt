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


class NativeViewHost(QtCore.QObject):
    activated = QtCore.pyqtSignal(object)
    closed = QtCore.pyqtSignal(object)

    def __init__(self, registry):
        super().__init__(registry)
        self.registry = registry
        self._registered = set()
        registry.activated.connect(self._activated)
        registry.closed.connect(self._closed)

    def register(self, dock):
        self._registered.add(dock.objectName())

    def create(self, view_id, title, widget, *, relative_to, closable=True):
        with self.registry.presentation_change():
            dock = self.registry.create(
                view_id,
                title,
                widget,
                QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
                closable=closable,
            )
            if not relative_to.isFloating():
                self.registry.window.tabifyDockWidget(relative_to, dock)
        self.register(dock)
        return dock

    def show(self, dock):
        self.registry.show(dock.objectName())

    def rename(self, dock, title):
        dock.setWindowTitle(title)

    def close(self, dock):
        dock.close()

    def remove(self, dock):
        key = dock.objectName()
        self._registered.discard(key)
        self.registry.remove(key)

    def _activated(self, key):
        if key in self._registered:
            self.activated.emit(self.registry[key])

    def _closed(self, key):
        if key in self._registered:
            self.closed.emit(self.registry[key])
