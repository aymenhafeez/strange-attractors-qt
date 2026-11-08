# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtWidgets


def app_settings():
    return QtCore.QSettings("Aymen Hafeez", "Systems analysis")


def clear(settings):
    settings.remove("layout")
    settings.remove("workspace")
    settings.remove("startup")
    settings.sync()


def _view_managers(console_panel):
    return (
        ("plot", "workspace/plots", console_panel.plots),
        ("view3d", "workspace/views3d", console_panel.views3d),
        ("table", "workspace/tables", console_panel.tables),
    )


def save_workspace(settings, console_panel):
    for kind, key, manager in _view_managers(console_panel):
        settings.setValue(f"workspace/default_{kind}", manager.default_name)
        settings.setValue(key, manager.names())

    kind, name = console_panel.active_view_key()
    settings.setValue("workspace/active_kind", kind)
    settings.setValue("workspace/active_name", name)

    script_panel = console_panel.script_panel
    settings.setValue(
        "workspace/open_scripts",
        [str(path) for path in script_panel.open_script_paths()],
    )
    script_path = script_panel.current_script_path()
    if script_path is not None:
        settings.setValue("workspace/current_script", str(script_path))
    else:
        settings.remove("workspace/current_script")


def restore_workspace(settings, console_panel):
    for kind, key, manager in _view_managers(console_panel):
        default = settings.value(f"workspace/default_{kind}", manager.default_name)
        manager.rename(manager.default_name, default)
        for name in settings.value(key, [], type=list):
            if name != default:
                manager.new(name, activate=False)

    kind = settings.value("workspace/active_kind", "plot")
    manager = console_panel.views3d if kind == "view3d" else console_panel.plots
    manager.activate(settings.value("workspace/active_name", "Plot"))

    console_panel.script_panel.restore_scripts(
        settings.value("workspace/open_scripts", [], type=list),
        settings.value("workspace/current_script"),
    )


def save(settings, window, dock_layout, console_panel, status_bar, mode):
    theme = QtWidgets.QApplication.instance().property("appTheme")
    settings.setValue("layout/plot_theme", theme)
    settings.setValue("layout/window_geometry", window.saveGeometry())
    settings.setValue("layout/status_bar", status_bar.process_visible)
    dock_layout.save(settings)
    settings.setValue("layout/workspace_mode", mode)
    save_workspace(settings, console_panel)


def restore(settings, window, dock_layout, console_panel, status_bar):
    geometry = settings.value("layout/window_geometry")
    if geometry is None:
        window.setWindowState(QtCore.Qt.WindowState.WindowMaximized)
    else:
        window.restoreGeometry(geometry)

    status_bar.set_process_visible(settings.value("layout/status_bar", True, type=bool))
    restore_workspace(settings, console_panel)
    dock_layout.restore(settings)


def saved_theme(settings):
    theme = settings.value("layout/plot_theme")
    return theme if theme in {"light", "dark"} else None


def saved_mode(settings):
    mode = settings.value("layout/workspace_mode", "system")
    return mode if mode in {"system", "explore"} else "system"
