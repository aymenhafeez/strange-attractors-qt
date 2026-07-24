import sys

from .app import Window
from .perf import configure_perf_logging
import pyqtgraph as pg


def main():
    configure_perf_logging()
    app = pg.mkQApp()
    app.setStyle("Fusion")
    w = Window()
    w.resize(1100, 800)
    w.showFullScreen() if "--fullscreen" in sys.argv else w.show()
    pg.exec()


if __name__ == "__main__":
    main()
