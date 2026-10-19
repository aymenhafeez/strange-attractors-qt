# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from uuid import uuid4

from pyqtgraph.Qt import QtCore, QtWidgets

from .style import dock_widget_style


class AppDock(QtWidgets.QDockWidget):
    activated = QtCore.pyqtSignal()

    def reveal(self):
        self.show()
        self.raise_()
        self.activated.emit()

    def mousePressEvent(self, a0):
        self.activated.emit()
        super().mousePressEvent(a0)


class DockLayout(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.docks = {}
        self.states = {}
        self.mode = None
        self._changing = False
        self.menu = QtWidgets.QMenu("Panels", window)
        window.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
        )
        window.setTabPosition(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.South,
        )
        window.tabifiedDockWidgetActivated.connect(self._activate)
        QtWidgets.QApplication.instance().focusChanged.connect(self._focus_changed)

    def add(self, name, title, widget, *, relative_to=None):
        if "/" in name and not name.startswith("analysis/"):
            name = f"{name.split('/', 1)[0]}/{uuid4().hex}"
        dock = AppDock(title, self.window)
        dock.setStyleSheet(dock_widget_style())
        dock.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        dock.setContentsMargins(1, 1, 1, 1)
        dock.setObjectName(name)
        dock.setWidget(widget)
        widget.show()

        self.docks[name] = dock
        dock.activated.connect(lambda: self._highlight_dock(dock))
        self.window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        if relative_to is not None:
            self.window.tabifyDockWidget(relative_to, dock)

        dock.hide()
        self.menu.addAction(dock.toggleViewAction())
        dock.visibilityChanged.connect(self.changed)

        return dock

    def remove(self, dock):
        self.docks.pop(dock.objectName())
        self.menu.removeAction(dock.toggleViewAction())
        self.window.removeDockWidget(dock)
        dock.deleteLater()

    def switch(self, mode):
        if mode == self.mode:
            return
        if self.mode is not None:
            self.states[self.mode] = self.window.saveState()

        self.mode = mode
        state = self.states.get(mode)

        self._changing = True
        for dock in self.docks.values():
            dock.hide()
        if state is None or not self.window.restoreState(state):
            self.reset()

        self._changing = False
        self.changed.emit()

    def reset(self):
        self._changing = True
        window = self.window
        docks = self.docks
        for dock in docks.values():
            dock.hide()
            dock.setFloating(False)
            window.removeDockWidget(dock)

        def add(name, area):
            dock = docks[name]
            window.addDockWidget(area, dock)
            return dock

        left = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
        bottom = QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        vertical = QtCore.Qt.Orientation.Vertical
        horizontal = QtCore.Qt.Orientation.Horizontal

        viewport = add("viewport", left)
        parameters = add("parameters", left)
        view_options = add("view_options", left)
        data = add("data", left)
        trajectories = add("trajectories", left)
        presets = add("presets", left)
        custom = add("custom", left)
        plot = add("plot", left)
        script = add("script", left)
        files = add("files", left)
        variables = add("variables", left)
        console = add("console", left)
        table = add("table", left)
        view3d = add("view3d", left)

        if self.mode == "system":
            window.splitDockWidget(parameters, viewport, horizontal)
            window.splitDockWidget(parameters, data, vertical)
            window.tabifyDockWidget(parameters, view_options)
            window.splitDockWidget(viewport, trajectories, horizontal)
            window.splitDockWidget(viewport, console, vertical)
            window.splitDockWidget(viewport, plot, horizontal)
            window.tabifyDockWidget(console, script)
            window.tabifyDockWidget(console, files)
            window.tabifyDockWidget(console, variables)
            window.splitDockWidget(trajectories, presets, vertical)
            window.tabifyDockWidget(presets, custom)
            visible = [
                viewport,
                parameters,
                view_options,
                data,
                trajectories,
                presets,
                custom,
            ]
        else:
            window.splitDockWidget(files, script, horizontal)
            window.splitDockWidget(script, plot, horizontal)
            window.splitDockWidget(plot, console, vertical)
            window.splitDockWidget(files, variables, vertical)
            visible = [files, variables, script, plot, console]

        window.tabifyDockWidget(plot, table)
        window.tabifyDockWidget(plot, view3d)
        placed = {
            dock.objectName()
            for dock in (
                viewport,
                parameters,
                view_options,
                data,
                trajectories,
                presets,
                custom,
                plot,
                script,
                files,
                variables,
                console,
                table,
                view3d,
            )
        }

        if self.mode == "system":
            poincare = add("analysis/poincare_panel", left)
            window.splitDockWidget(viewport, poincare, vertical)

        for name in docks:
            if name in placed:
                continue
            if self.mode == "system" and name == "analysis/poincare_panel":
                continue

            dock = add(name, bottom if name == "output" else left)
            if name != "output":
                window.tabifyDockWidget(
                    viewport if name.startswith("analysis/") else plot, dock
                )

        for dock in visible:
            dock.show()

        parameters.raise_()
        presets.raise_()
        console.raise_()
        plot.raise_()
        self.resize_defaults()
        QtCore.QTimer.singleShot(0, self.resize_defaults)
        self._changing = False
        self.changed.emit()

    def resize_defaults(self):
        docks = self.docks
        width = self.window.width()
        height = self.window.height()
        horizontal = QtCore.Qt.Orientation.Horizontal
        vertical = QtCore.Qt.Orientation.Vertical

        if self.mode == "system":
            workspace_open = not docks["plot"].isHidden()
            columns = [docks["parameters"], docks["viewport"]]
            sizes = [int(width * 0.22), int(width * (0.28 if workspace_open else 0.56))]
            if workspace_open:
                columns.append(docks["plot"])
                sizes.append(int(width * 0.28))
            columns.append(docks["trajectories"])
            sizes.append(int(width * 0.22))
            self.window.resizeDocks(columns, sizes, horizontal)
            self.window.resizeDocks(
                [docks["parameters"], docks["data"]],
                [int(height * 0.5), int(height * 0.5)],
                vertical,
            )
            self.window.resizeDocks(
                [docks["trajectories"], docks["presets"]],
                [int(height * 0.5), int(height * 0.5)],
                vertical,
            )
            if workspace_open:
                self.window.resizeDocks(
                    [docks["viewport"], docks["console"]],
                    [int(height * 0.65), int(height * 0.35)],
                    vertical,
                )
        else:
            self.window.resizeDocks(
                [docks["files"], docks["script"], docks["plot"]],
                [int(width * 0.2), int(width * 0.45), int(width * 0.35)],
                horizontal,
            )
            self.window.resizeDocks(
                [docks["files"], docks["variables"]],
                [int(height * 0.5), int(height * 0.5)],
                vertical,
            )
            self.window.resizeDocks(
                [docks["plot"], docks["console"]],
                [int(height * 0.6), int(height * 0.4)],
                vertical,
            )

    def save(self, settings):
        settings.setValue(
            "layout/dock_ids",
            {
                f"{name.split('/', 1)[0]}/{dock.windowTitle()}": name
                for name, dock in self.docks.items()
                if "/" in name and not name.startswith("analysis/")
            },
        )
        self.states[self.mode] = self.window.saveState()
        for mode, state in self.states.items():
            settings.setValue(f"layout/docks/{mode}", state)

    def restore(self, settings):
        dock_ids = settings.value("layout/dock_ids", {})

        for dock in self.docks.values():
            name = dock.objectName()
            if "/" in name and not name.startswith("analysis/"):
                key = f"{name.split('/', 1)[0]}/{dock.windowTitle()}"
                dock.setObjectName(dock_ids.get(key, name))

        self.docks = {dock.objectName(): dock for dock in self.docks.values()}

        for mode in ("system", "explore"):
            state = settings.value(f"layout/docks/{mode}")
            if state is not None:
                self.states[mode] = state

    def _activate(self, dock):
        if not self._changing:
            dock.activated.emit()

    def _focus_changed(self, _old, widget):
        if self._changing:
            return

        while widget is not None:
            if isinstance(widget, AppDock):
                widget.activated.emit()
                break
            widget = widget.parentWidget()

    def _highlight_dock(self, active_dock):
        if self._changing:
            return

        for dock in self.docks.values():
            active = dock is active_dock
            if dock.property("activeDock") == active:
                continue

            dock.setProperty("activeDock", active)
            # Reapply the sheet to refresh the cached title bar button icons too.
            dock.setStyleSheet(dock.styleSheet())
            dock.update()
