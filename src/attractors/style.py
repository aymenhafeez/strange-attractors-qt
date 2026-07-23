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

SPLITTER_HANDLE = """
    QSplitter::handle {
        background-color: transparent;
    }
    QSplitter::handle:horizontal {
        width: 3px;
    }
    QSplitter::handle:vertical {
        height: 3px;
    }
    QSplitter::handle:hover {
        background-color: palette(highlight);
    }
"""

LYAPUNOV_PLOT = "background-color: rgba(0, 0, 0, 0); border: 0px"

CUSTOM_PANEL = """
    QWidget#customPanelContent {
        background-color: rgba(0, 0, 0, 240);
        border: 1px solid #aaa;
        border-radius: 0px;
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
