import sys

from .app import Window, WINDOW_WIDTH, WINDOW_HEIGHT
from .perf import configure_perf_logging
import pyqtgraph as pg


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
