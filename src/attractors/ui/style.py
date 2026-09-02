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
            "plot_auto_pens": ("w", "r", "g", "b", "c", "m", "y"),
            "trajectory_palette": DARK_TRAJECTORY_PALETTE,
        }

    return {
        "is_dark": False,
        "plot_background": "#ffffff",
        "gl_background": (255, 255, 255, 255),
        "gl_grid_face": (1.0, 1.0, 1.0, 1.0),
        "gl_grid_line": (0.65, 0.65, 0.65, 1.0),
        "gl_axis_label": (0.0, 0.0, 0.0, 1.0),
        "trajectory": (0.05, 0.05, 0.05),
        "plot_grid_alpha": 0.5,
        "plot_pen": "k",
        "scatter_brush": "black",
        "plot_auto_pens": ("k", "r", "g", "b", "c", "m", "y"),
        "trajectory_palette": LIGHT_TRAJECTORY_PALETTE,
    }


if plot_colours()["is_dark"]:
    EQUATION_LABEL = """
        color: #ddd;
        font-size: 13px;
        padding: 2px 6px;
        background: rgba(0, 0, 0, 0);
    border: 0px;
    border-radius: 0px;
    """
else:
    EQUATION_LABEL = """
        color: #000;
        font-size: 13px;
        padding: 2px 6px;
        background: rgba(0, 0, 0, 0);
        border: 0px;
        border-radius: 0px;
    """

SPLITTER_HANDLE_HOVER = """
    QSplitter::handle:hover {
        background-color: palette(highlight);
    }
"""

SCENE_TOOLBAR = """
    QToolBar#sceneToolbar {
        border: 0px;
        border-bottom: 0px;
    }
"""

SIDE_PANEL = """
    QWidget#controlPanel {
        background: palette(window);
    }

    QWidget#controlPanelSliders {
        background: palette(base);
    }
"""

RIGHT_PANEL = """
    QTextEdit, QDoubleSpinBox {
        background: palette(window);
        border: 1px solid palette(mid);
        padding: 2px 4px;
    }
"""

PANEL_SURFACE = """
    QWidget#panelSurface {
        background: palette(base);
        border: 1px solid palette(mid);
    }

    QWidget#panelSurface QLineEdit,
    QWidget#panelSurface QTextEdit,
    QWidget#panelSurface QAbstractSpinBox {
        background: palette(window);
        border: 1px solid palette(mid);
        padding: 2px 4px;
    }
"""

TABLE_VIEW = """
    QWidget#dataViewPanel {
        background: palette(base);
        border: 1px solid palette(mid);
    }

    QTableView {
        background: palette(base);
        border: 1px solid palette(mid);
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

CONSOLE_PLOT_PARAMS = """
    QFrame#ConsolePlotParams {
        border-top: 2px solid palette(mid);
    }
"""
