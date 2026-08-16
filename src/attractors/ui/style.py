from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


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


EQUATION_LABEL = """
    color: #ddd;
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
