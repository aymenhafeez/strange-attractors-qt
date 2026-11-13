# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

"""Subclass for managing console plots, views and tables"""

from pyqtgraph.Qt import QtCore


class DockedViewManager(QtCore.QObject):
    views_changed = QtCore.pyqtSignal()
    current_changed = QtCore.pyqtSignal(str)
    view_removed = QtCore.pyqtSignal(str, object)
    view_cleared = QtCore.pyqtSignal(str, object)

    kind = "view"
    name_prefix = "View"
    dock_prefix = "view"
    active_kind = None

    def __init__(
        self,
        dock_layout,
        default_name,
        default_view,
        default_dock,
        status_callback=None,
        active_callback=None,
    ):
        super().__init__(dock_layout)
        self._dock_layout = dock_layout
        self._views = {default_name: default_view}
        self._docks = {default_name: default_dock}
        self._default_name = default_name
        self._current_name = default_name
        self._status_callback = status_callback
        self._active_callback = active_callback
        self._connect_view(default_view)

    def __repr__(self):
        return f"{type(self).__name__}(current={self._current_name!r})"

    @property
    def current(self):
        return self._views[self._current_name]

    @property
    def current_name(self):
        return self._current_name

    @property
    def default_name(self):
        return self._default_name

    def names(self):
        return list(self._views)

    def views(self):
        return list(self._views.values())

    def docks(self):
        return list(self._docks.values())

    def get(self, name, *, activate=True):
        key = self._key(name)
        try:
            view = self._views[key]
        except KeyError as exc:
            raise KeyError(f"No console {self.kind} named {key!r}") from exc

        if activate:
            self._mark_active()
            self._set_current_name(key)
            self._docks[key].reveal()

        return view

    def rename(self, old_name, new_name):
        old_key = self._key(old_name)
        new_key = self._key(new_name)
        if old_key not in self._views:
            raise KeyError(f"No console {self.kind} named {old_key!r}")
        if new_key != old_key and new_key in self._views:
            raise ValueError(f"Console {self.kind} {new_key!r} already exists")

        if new_key == old_key:
            self._set_current_name(new_key)
            return self._views[new_key]

        self._mark_active()

        view = self._views.pop(old_key)
        dock = self._docks.pop(old_key)
        self._views[new_key] = view
        self._docks[new_key] = dock

        if old_key == self._default_name:
            self._default_name = new_key
        if old_key == self._current_name:
            self._current_name = new_key

        dock.setWindowTitle(new_key)
        self.views_changed.emit()
        self.current_changed.emit(self._current_name)

        return view

    # need to return the existing view when the name is takne for session_store
    def new(self, name=None, *, activate=True):
        key = self._next_name() if name is None else self._key(name)
        if key in self._views:
            return self.get(key, activate=activate)

        view = self._make_view()
        self._connect_view(view)
        dock = self._dock_layout.add(
            f"{self.dock_prefix}/{key}",
            key,
            view.host,
            relative_to=self._docks[self._default_name],
        )
        dock.activated.connect(lambda: self.activate(dock.windowTitle()))
        dock.closed.connect(lambda: self.close(dock.windowTitle()))

        self._views[key] = view
        self._docks[key] = dock
        if activate:
            self._mark_active()
            self._set_current_name(key)
            dock.reveal()
        self.views_changed.emit()

        return view

    def activate(self, name):
        key = self._key(name)
        if key not in self._views:
            return

        self._set_current_name(key)
        self._mark_active()

    def close(self, name=None):
        key = self._current_name if name is None else self._key(name)
        if key == self._default_name:
            view = self._views[key]
            view.clear()
            self.view_cleared.emit(key, view)
            self._set_current_name(key)
            return

        dock = self._docks[key]
        self._forget(key)
        self._dock_layout.remove(dock)

    def clear(self):
        view = self.current
        view.clear()
        self.view_cleared.emit(self._current_name, view)

    def clear_all(self):
        for name, view in self._views.items():
            view.clear()
            self.view_cleared.emit(name, view)

    def set_status_callback(self, callback):
        self._status_callback = callback

    def _make_view(self):
        raise NotImplementedError

    def _connect_view(self, view):
        # called for the default view and every view from new()
        # not needed for tables
        pass

    def _mark_active(self):
        if self._active_callback is not None:
            self._active_callback(self.active_kind)

    def _set_current_name(self, key):
        if self._current_name == key:
            return

        self._current_name = key
        self.current_changed.emit(key)

    def _forget(self, name):
        if name == self._default_name or name not in self._views:
            return

        view = self._views.pop(name)
        self._docks.pop(name)
        if self._current_name == name:
            self._set_current_name(self._default_name)

        self.view_removed.emit(name, view)
        self.views_changed.emit()

    def _next_name(self):
        index = 2
        while f"{self.name_prefix} {index}" in self._views:
            index += 1

        return f"{self.name_prefix} {index}"

    def _key(self, name):
        key = str(name).strip()
        if not key:
            raise ValueError(f"{self.kind.capitalize()} name can't be empty")

        return key
