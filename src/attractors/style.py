EQUATION_LABEL = """
    color: #ddd;
    font-size: 13px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 120);
    border-radius: 0px;
    border-left: 0px;
    border-top: 0px;
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
    QWidget#controlPanel {
        background-color: #000000;
        border: 1px solid #aaa;
        border-left: 2px solid #999;
    }
    QSlider:horizontal {
        min-height: 10px;
        max-height: 10px;
    }
    QSlider::handle:horizontal {
        background: #ddd;
        width: 5px;
        min-height: 14px;    /* slightly taller than groove */
        max-height: 14px;
        margin: -2px 0;      /* let the handle overlap the groove */
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

ALPHA_SLIDER = "color: white; font-weight: bold;"

LINE_MODE_CHECKBOX = "color: white;"

SPLITTER = "QSplitter::handle { width: 1px; background: #555; }"

CONTAINER = "border: 1px solid #aaa;"

LYAPUNOV_LABEL = """
    color: #ddd;
    font-size: 13px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 120);
    border-radius: 0px;
"""
