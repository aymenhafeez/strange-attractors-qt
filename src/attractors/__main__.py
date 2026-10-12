import argparse

import pyqtgraph as pg

from .app import WINDOW_HEIGHT, WINDOW_WIDTH, Window, app_settings
from .perf import configure_perf_logging
from .systems.registry import ATTRACTORS
from .ui.output_panel import CaptureOutput


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset", action="store_true", help="Run with fresh session state"
    )
    parser.add_argument("--explore", action="store_true", help="Run explore workspace")
    parser.add_argument("--system", action="store_true", help="Run system workspace")
    parser.add_argument("--default", action="store_true", help="Run with the default layout")
    parser.add_argument("--fullscreen", action="store_true", help="Run in fullscreen")
    parser.add_argument("--attractor", type=str, choices=ATTRACTORS, help="Load a specific attractor")
    args = parser.parse_args()

    # needs to go before constructing the window
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

    actions = {
        "explore": lambda: w._set_workspace_mode("explore"),
        "system": lambda: w._set_workspace_mode("system"),
        "default": w._restore_default_layout,
        "attractor": lambda: w.controls._on_attractor_selected(args.attractor)
    }

    for name, func in actions.items():
        if getattr(args, name):
            func()

    capture_output = CaptureOutput(w.output_panel)
    capture_output.install()

    configure_perf_logging()

    w.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    w.showFullScreen() if args.fullscreen else w.show()
    pg.exec()


if __name__ == "__main__":
    main()
