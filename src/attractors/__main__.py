import sys

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from .app import WINDOW_HEIGHT, WINDOW_WIDTH, Window
from .perf import configure_perf_logging


def main():
    configure_perf_logging()
    QtCore.QCoreApplication.setAttribute(
        QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
    )
    app = pg.mkQApp()
    # set the app name strange-attractors for now so the standard path writable location
    # doesn't need to be changed
    app.setApplicationName("strange-attractors")
    app.setStyle("Fusion")
    w = Window()
    w.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    w.showFullScreen() if "--fullscreen" in sys.argv else w.show()
    pg.exec()


if __name__ == "__main__":
    main()
