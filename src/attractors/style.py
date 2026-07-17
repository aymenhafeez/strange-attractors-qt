EQUATION_LABEL = """
    color: #ddd;
    font-size: 13px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0);
    border: 0px;
    border-radius: 0px;
"""

STATUS_BAR = "background-color: #000000;"

STATUS_PARAMS = "color: #aaa; font-size: 12px;"

STATUS_SYSTEM = """
    color: #aaa;
    font-size: 13px;
    border-left: 0px;
"""

STATUS_IC = """
    color: #aaa;
    font-size: 13px;
    border-right: 0px;
"""

SLIDERS = """
    #controlPanel {
        background-color: #000000;
        border: 1px solid #aaa;
        border-left: 2px solid #999;
    }
"""

DROPDOWN_BOX = """
    QPushButton {
        background-color: #000000;
        color: white;
        border: 1px solid #aaa;
        border-radius: 0px;
        padding: 4px 8px;
        text-align: left;
    }
"""

DROPDOWN_SELECTION = """
    QMenu {
        background-color: #000000;
        border: 1px solid #aaa;
    }
    QMenu::item {
        background-color: #000000;
        color: white;
        padding: 4px 20px;
    }
    QMenu::item:selected {
        background-color: #dddddd;
        color: #000000;
    }
"""

ATTRACTOR_INFO = "color: #ddd; font-size: 13px"

SLIDER_PARAMS = "color: white; font-weight: bold;"

LINE_MODE_CHECKBOX = "color: white;"

SPLITTER = "QSplitter::handle { width: 1px; background: #555; }"

CONTAINER = "border: 1px solid #aaa;"

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

FLAT_BUTTON = """
    QPushButton {
        background-color: #ddd;
        color: black;
        border: 1px solid #aaa;
        border-radius: 0px;  /* The key change */
        padding: 4px 12px;
    }
    QPushButton:hover {
        background-color: #eee;
    }
    QPushButton:pressed {
        background-color: #ccc;
    }
"""
