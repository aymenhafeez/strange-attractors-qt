EQUATION_LABEL = """
    color: #ddd;
    font-size: 13px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0);
    border-radius: 0px;
    border-left: 0px;
    border-top: 0px;
"""

STATUS_BAR = "background-color: #000000;"

STATUS_PARAMS = "color: #aaa; font-size: 11px;"

STATUS_SYSTEM = """
    color: #aaa;
    font-size: 12px;
    border-left: 0px;
"""

STATUS_IC = """
    color: #aaa;
    font-size: 12px;
    border-right: 0px;
"""

SLIDERS = """
    QWidget#controlPanel {
        background-color: #000000;
        border: 1px solid #555;
    }
    QSlider:horizontal {
        min-height: 30px;
        max-height: 30px;
    }
    QSlider::handle:horizontal {
        background: #ddd;
        width: 5px;
        min-height: 30px;
        max-height: 30px;
        margin: 0;
    }
    QSlider::sub-page:horizontal {
        background: #ddd;
    }
    QSlider::add-page:horizontal {
        background: #888;
    }
"""

DROPDOWN_BOX = """
    QPushButton {
        background-color: #000000;
        color: white;
        border: 1px solid #555;
        border-radius: 0px;
        padding: 4px 8px;
        text-align: left;
    }
"""

DROPDOWN_SELECTION = """
    QMenu {
        background-color: #000000;
        border: 1px solid #555;
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

ATTRACTOR_INFO = "color: #ddd; font-size: 12px"

SLIDER_PARAMS = "color: white; font-weight: bold;"

SLIDER_VALS = "color: white; font-weight: bold;"

ALPHA_SLIDER = "color: white; font-weight: bold;"

LINE_MODE_CHECKBOX = "color: white;"

SPLITTER = "QSplitter::handle { width: 1px; background: #555; }"

CONTAINER = "border: 1px solid #555;"
