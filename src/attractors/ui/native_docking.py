from contextlib import contextmanager

from pyqtgraph.Qt import QtCore, QtWidgets


class NativeDock(QtWidgets.QDockWidget):
    closed = QtCore.pyqtSignal(object)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()


class DockRegistry(QtCore.QObject):
    activated = QtCore.pyqtSignal(str)
    open_chaged = QtCore.pyqtSignal(str, bool)
    closed = QtCore.pyqtSignal(str)

    def __init__(self, window):
        self.window = window
        self._docks = {}
        self._presentation_depth = 0

        window.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
        )
        window.tabifiedDockWidgetActivated.connect(self._tab_activated)

    @property
    def changing_presentation(self):
        return self._presentation_depth > 0

    @contextmanager
    def presentation_change(self):
        self._presentation_depth = 1
        try:
            yield
        finally:
            self._presentation_depth -= 1

    def __getitem__(self, key):
        return self._docks[key]

    def __contains__(self, key):
        return key in self._docks

    def create(self, key, title, widget, area, *, closable=True):
        if key in self._docks:
            raise ValueError(f"Duplicate dock ID: {key}")

        dock = NativeDock(title, self.window)
        dock.setObjectName(key)
        features = (
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        if closable:
            features |= QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
        dock.setFeatures(features)
        dock.setWidget(widget)
        self._docks[key] = dock
        self.window.addDockWidget(area, dock)

        widget.show()
        dock.hide()
        dock.toggleViewAction().toggled.connect(
            lambda opened, key=key: self._open_changed(key, opened)
        )

        return dock

    def _tab_activated(self, dock):
        key = dock.objectName()
        if self._docks.get(key) is dock and not self.changing_presentation:
            self.activated.emit(key)

    def _open_changed(self, key, opened):
        if not self.changing_presentation:
            self.open_chaged.emit(key, opened)
