EQUATION_LABEL = """
    color: #ddd;
    font-size: 13px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0);
    border: 0px;
    border-radius: 0px;
"""

ATTRACTOR_INFO = "color: #ddd; font-size: 13px"

SLIDER_PARAMS = "color: white; font-weight: bold;"

CONTAINER = "background: #000; border: none;"

SPLITTER_HANDLE_HOVER = """
    QSplitter::handle:hover {
        background-color: palette(highlight);
    }
"""

LYAPUNOV_PLOT = "background-color: rgba(0, 0, 0, 0); border: 0px"

SCENE_TOOLBAR = """
    QToolBar#sceneToolbar {
        border: 0px;
        border-bottom: 0px;
    }
"""

DOCK_BORDER_COLOUR = "palette(mid)"

DOCK_HORIZONTAL = f"""
    Dock > QWidget {{
        border: 1px solid {DOCK_BORDER_COLOUR};
        border-radius: 5px;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-top-width: 0px;
    }}
"""

DOCK_VERTICAL = f"""
    Dock > QWidget {{
        border: 1px solid {DOCK_BORDER_COLOUR};
        border-radius: 5px;
        border-top-left-radius: 0px;
        border-bottom-left-radius: 0px;
        border-left-width: 0px;
    }}
"""

DOCK_NO_TITLE = f"""
    Dock > QWidget {{
        border: 1px solid {DOCK_BORDER_COLOUR};
        border-radius: 5px;
    }}
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

CUSTOM_TOGGLE = """
    QPushButton {
        background-color: rgba(0, 0, 0, 180);
        color: white;
        border: 1px solid #aaa;
        border-radius: 0px;
        padding: 3px 8px;
        font-size: 12px;
        text-align: left;
    }
    QPushButton:hover {
        color: white;
        background-color: rgba(40, 40, 40, 220);
    }
"""

NO_BORDER = "border: none;"

CONSOLE_PLOT_WIDGET = """
    PlotWidget#ConsolePlotWidget {
        border: 2px solid palette(mid);
    }
"""

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
        background: palette(window);
        border-top: 2px solid palette(mid);
    }

    QLabel#ConsolePlotParamTitle {
        color: palette(text);
        font-weight: bold;
        padding-left: 2px;
    }

    QDoubleSpinBox {
        background: palette(window);
    }

    QFrame#ConsolePlotParamControls {
        background: palette(base);
        border: 1px solid palette(mid);
    }
"""
