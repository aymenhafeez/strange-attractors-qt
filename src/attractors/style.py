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
    QScrollArea#sidePanelScroll {
        background: transparent;
        border: 1px solid palette(mid);
        border-radius: 6px;
        padding: 2px;
    }
    QScrollArea#sidePanelScroll > QWidget {
        background: transparent;
    }
"""

CUSTOM_PANEL = """
    QWidget#customPanelContent {
        background-color: rgba(0, 0, 0, 240);
        border: 1px solid #aaa;
        border-radius: 6px;
    }
    QWidget#rowsContainer {
        border: none;
        background: transparent;
    }
    QLabel {
        color: white;
        border: none;
    }
    QTextEdit {
        background-color: white;
        color: #333;
        border: 1px solid #aaa;
    }
    QDoubleSpinBox {
        background-color: white;
        color: #333;
        border: 1px solid #aaa;
    }
    QPushButton {
        background-color: #ddd;
        color: black;
        border: 1px solid #aaa;
        padding: 4px 12px;
    }
    QPushButton:hover {
        background-color: #eee;
    }
    QPushButton:pressed {
        background-color: #ccc;
    }
    QCheckBox {
        border: none;
        color: white;
    }
    QCheckBox::indicator {
        width: 13px;
        height: 13px;
        background-color: white;
        border: 1px solid #aaa;
    }
    QCheckBox::indicator:checked {
        background-color: #4a90d9;
        border: 1px solid #2a6099;
    }
    QCheckBox::indicator:hover {
        border: 1px solid #4a90d9;
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
