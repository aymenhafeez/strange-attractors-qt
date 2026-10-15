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
    open_changed = QtCore.pyqtSignal(str, bool)
    closed = QtCore.pyqtSignal(str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._docks = {}
        self._open_states = {}
        self._presentation_depth = 0

        window.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
        )
        window.tabifiedDockWidgetActivated.connect(self._tab_activated)
        QtWidgets.QApplication.instance().installEventFilter(self)
        window.destroyed.connect(self.dispose)

    @property
    def changing_presentation(self):
        return self._presentation_depth > 0

    @contextmanager
    def presentation_change(self):
        self._presentation_depth += 1
        try:
            yield
        finally:
            self._presentation_depth -= 1

    def __getitem__(self, key):
        return self._docks[key]

    def __contains__(self, key):
        return key in self._docks

    def items(self):
        return tuple(self._docks.items())

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

        self._open_states[key] = False
        with self.presentation_change():
            self.window.addDockWidget(area, dock)
            widget.show()
            dock.hide()
        dock.toggleViewAction().toggled.connect(
            lambda _checked, key=key: self._refresh_open_state(key)
        )

        dock.closed.connect(lambda _dock, key=key: self.closed.emit(key))

        return dock

    def _refresh_open_state(self, key):
        if key not in self._docks:
            return

        opened = self.is_open(key)
        if self._open_states.get(key) == opened:
            return

        self._open_states[key] = opened
        if not self.changing_presentation:
            self.open_changed.emit(key, opened)

    def _tab_activated(self, dock):
        key = dock.objectName()
        if self._docks.get(key) is dock and not self.changing_presentation:
            self.activated.emit(key)

    def is_open(self, key):
        # using this instead of overriding isVIsible() so it can work before the main window is shown
        return not self[key].isHidden()

    def show(self, key, *, activate=True):
        dock = self[key]
        dock.show()
        self._refresh_open_state(key)
        if activate:
            dock.raise_()
            if not self.changing_presentation:
                self.activated.emit(key)

    def hide(self, key):
        self[key].hide()

    def remove(self, key):
        dock = self._docks.pop(key)
        self._open_states.pop(key)
        self.window.removeDockWidget(dock)
        dock.deleteLater()

    def eventFilter(self, watched, event):
        if "_docks" not in self.__dict__ or "_presentation_depth" not in self.__dict__:
            return False
        if isinstance(watched, NativeDock) and event.type() in {
            QtCore.QEvent.Type.ShowToParent,
            QtCore.QEvent.Type.HideToParent,
        }:
            key = next(
                (key for key, dock in self._docks.items() if dock is watched), None
            )
            if key is not None:
                self._refresh_open_state(key)

        if not self.changing_presentation and event.type() in {
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QEvent.Type.FocusIn,
        }:
            widget = watched if isinstance(watched, QtWidgets.QWidget) else None
            while widget is not None:
                if isinstance(widget, NativeDock):
                    key = widget.objectName()
                    if self._docks.get(key) is widget:
                        self.activated.emit(key)
                    break
                widget = widget.parentWidget()

        return super().eventFilter(watched, event)

    def keys(self):
        return tuple(self._docks)

    def __iter__(self):
        return iter(tuple(self._docks))

    def values(self):
        return tuple(self._docks.values())

    def dispose(self):
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
