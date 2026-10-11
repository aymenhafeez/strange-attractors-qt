import argparse
import sys

import pyqtgraph as pg

from .app import WINDOW_HEIGHT, WINDOW_WIDTH, Window, app_settings
from .perf import configure_perf_logging
from .ui.output_panel import CaptureOutput


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset", action="store_true", help="Run with fresh session state"
    )
    args = parser.parse_args()
    if args.reset:
        settings = app_settings()
        settings.remove("layout")
        settings.remove("workspace")
        settings.sync()

    app = pg.mkQApp()
    # set the app name strange-attractors for now so the standard path writable location
    # doesn't need to be changed
    app.setApplicationName("strange-attractors")
    app.setStyle("Fusion")
    w = Window()

    capture_output = CaptureOutput(w.output_panel)
    capture_output.install()

    configure_perf_logging()

    w.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    w.showFullScreen() if "--fullscreen" in sys.argv else w.show()
    pg.exec()


if __name__ == "__main__":
    main()
