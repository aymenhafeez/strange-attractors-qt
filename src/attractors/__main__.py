import sys

import pyqtgraph as pg

from .app import WINDOW_HEIGHT, WINDOW_WIDTH, Window
from .perf import configure_perf_logging


def main():
    configure_perf_logging()
    app = pg.mkQApp()
    app.setStyle("Fusion")
    w = Window()
    w.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    w.showFullScreen() if "--fullscreen" in sys.argv else w.show()
    pg.exec()


if __name__ == "__main__":
    main()
