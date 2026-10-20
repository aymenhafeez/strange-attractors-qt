# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

DARK_TRAJECTORY_PALETTE = (
    QtGui.QColor("#3b82f6"),
    QtGui.QColor("#f97316"),
    QtGui.QColor("#10b981"),
    QtGui.QColor("#ef4444"),
    QtGui.QColor("#8b5cf6"),
    QtGui.QColor("#06b6d4"),
    QtGui.QColor("#ec4899"),
    QtGui.QColor("#eab308"),
)

LIGHT_TRAJECTORY_PALETTE = (
    QtGui.QColor("#2563eb"),
    QtGui.QColor("#c2410c"),
    QtGui.QColor("#047857"),
    QtGui.QColor("#b91c1c"),
    QtGui.QColor("#7c3aed"),
    QtGui.QColor("#0891b2"),
    QtGui.QColor("#be185d"),
    QtGui.QColor("#a16207"),
)


def is_dark_mode():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False

    override = app.property("appTheme")
    if override == "dark":
        return True
    if override == "light":
        return False

    scheme = app.styleHints().colorScheme()
    if scheme != QtCore.Qt.ColorScheme.Unknown:
        return scheme == QtCore.Qt.ColorScheme.Dark

    palette = app.palette()
    window = palette.color(QtGui.QPalette.ColorRole.Window)
    text = palette.color(QtGui.QPalette.ColorRole.WindowText)

    return window.lightness() < text.lightness()


def plot_colours():
    if is_dark_mode():
        return {
            "is_dark": True,
            "plot_background": "#000000",
            "gl_background": (0, 0, 0, 255),
            "gl_grid_face": (0.0, 0.0, 0.0, 1.0),
            "gl_grid_line": (0.3, 0.3, 0.3, 1.0),
            "gl_axis_label": (0.86, 0.86, 0.86, 1.0),
            "trajectory": (1.0, 1.0, 1.0),
            "plot_grid_alpha": 0.25,
            "plot_pen": "w",
            "scatter_brush": "white",
            "scatter_size": 1,
            "plot_auto_pens": ("w", "r", "g", "b", "c", "m", "y"),
            "trajectory_palette": DARK_TRAJECTORY_PALETTE,
            "cmap": "CMRmap",
            "console_theme": "linux",
            "crosshair": "yellow",
            "label_text": "yellow",
            "colourbar_text": "white",
        }

    return {
        "is_dark": False,
        "plot_background": "#ffffff",
        "gl_background": (255, 255, 255, 255),
        "gl_grid_face": (1.0, 1.0, 1.0, 1.0),
        "gl_grid_line": (0.65, 0.65, 0.65, 1.0),
        "gl_axis_label": (0.0, 0.0, 0.0, 1.0),
        "trajectory": (0.24, 0.25, 0.57),
        "plot_grid_alpha": 0.35,
        "plot_pen": "#0e275b",
        "scatter_brush": "#0e275b",
        "scatter_size": 2,
        "plot_auto_pens": ("k", "r", "g", "b", "c", "m", "y"),
        "trajectory_palette": LIGHT_TRAJECTORY_PALETTE,
        "cmap": "CMRmap_r",
        "console_theme": "lightbg",
        "crosshair": "#c87b00",
        "label_text": "white",
        "colourbar_text": "black",
    }


def equation_label():
    colour = "#ddd" if is_dark_mode() else "#000"
    return f"""
        color: {colour};
        font-size: 13px;
        padding: 2px 6px;
        border: 0px;
        border-radius: 0px;
    """


def dock_widget_style():
    active = "#3f4349" if is_dark_mode() else "#f0f0f0"
    inactive = "#30343a" if is_dark_mode() else "#dee0e2"

    return f"""
        QDockWidget {{
            border: 1px solid palette(mid);
        }}
        QDockWidget[activeDock="true"] {{
            border: 1px solid palette(accent);
        }}

        QDockWidget::title {{
            background: {inactive};
            color: palette(window-text);
            border: 1px solid palette(mid);
            border-bottom: 0px;
            border-right: 0px;
            text-align: center;
            padding: 1px 1px;
        }}
        QDockWidget[activeDock="true"]::title {{
            background: {active};
            border: 1px solid palette(accent);
            border-bottom: 0px;
            border-right: 0px;
        }}
    """


MAIN_WINDOW = """
    QMainWindow::separator {
        width: 5px;
    }

    QMainWindow::separator:hover {
        background: palette(accent);
    }
"""

TAB_WIDGET = """
    border-right: 0px;
    border-left: 0px;
    border-top: 0px;
"""

SCENE_TOOLBAR = """
    QToolBar#sceneToolbar {
        padding: 5px 5px;
        border: 0px;
    }
"""

MENUBAR = """
    QMenuBar {
        background: palette(accent);
        color: white;
        padding: 2px 2px;
        border: 0px;
    }
"""

SIDE_PANEL = """
    QWidget#controlPanel {
        background: palette(window);
    }

    QWidget#controlPanelSliders {
        background: palette(base);
    }

    QWidget#sidePanelControlsScroll {
        border: 0px;
    }
"""

RIGHT_PANEL = """
    QTextEdit, QDoubleSpinBox {
        background: palette(window);
        border: 0px;
        padding: 2px 4px;
    }
"""

PANEL_SURFACE = """
    QWidget#panelSurface {
        background: palette(base);
        border: 0px;
    }
"""

SCRIPT_PANEL = """
    QWidget#scriptPanel {
        border: 0px;
    }

    QWidget#scriptPanel QLineEdit,
    QWidget#scriptPanel QTextEdit,
    QWidget#scriptPanel QAbstractSpinBox {
        background: palette(window);
        border: 0px;
        padding: 2px 4px;
    }
"""

FILE_TREE = """
    QWidget#fileTree {
        border: 0px;
    }

    QWidget#fileTree QLineEdit,
    QWidget#fileTree QTextEdit,
    QWidget#fileTree QAbstractSpinBox {
        background: palette(window);
        border: 0px;
        padding: 2px 4px;
    }
"""

FILE_SEARCH = """
    background: palette(base);
    border: 1px solid palette(mid);
"""

TABLE_VIEW = """
    QWidget#dataViewPanel {
        background: palette(base);
        border: 0px;
    }

    QTableView {
        background: palette(base);
        border: 0px;
    }

    QTabWidget::pane {
        border: 0px;
        background: palette(base);
    }
"""

# CONSOLE_PLOT_WIDGET = """
#     PlotWidget#ConsolePlotWidget {
#         border: 2px solid palette(mid);
#     }
# """

# CONSOLE_PLOT_PARAMS = """
#     QFrame#ConsolePlotParams {
#         background: black;
#         color: white;
#     }
#
#     QLabel#ConsolePlotParamTitle {
#         color: white;
#         font-weight: bold;
#         padding-left: 2px;
#     }
#
#     QFrame#ConsolePlotParamControls {
#         background: black;
#         border: 1px solid palette(mid);
#         color: white;
#     }
#
#     QLabel {
#         color: white;
#     }
#
#     QToolButton,
#     QDoubleSpinBox {
#         color: white;
#         background: #2b2b2b;
#         border: 1px solid #4a4a4a;
#         padding: 1px 6px;
#     }
#
#     QSlider::add-page:horizontal {
#         background: #2b2b2b;
#     }
# """
