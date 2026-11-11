# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import argparse

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from .app import Window
from .perf import configure_perf_logging
from .systems.registry import ATTRACTORS
from .ui import session_store
from .ui.output_panel import CaptureOutput

ANALYSIS_MODES = {
    "Lyapunov": "lyapunov_panel",
    "Projection": "projection_panel",
    "Poincare": "poincare_panel",
    "Bifurcation": "bifurcation_panel",
    "Signal": "signal_panel",
    "Trajectory": "trajectory_analysis_panel",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset", action="store_true", help="Run with fresh session state"
    )
    parser.add_argument("--explore", action="store_true", help="Run explore workspace")
    parser.add_argument("--system", action="store_true", help="Run system workspace")
    parser.add_argument(
        "--default",
        action="store_true",
        help="Run with the default layout without resetting session state",
    )
    parser.add_argument("--fullscreen", action="store_true", help="Run in fullscreen")
    parser.add_argument(
        "--attractor", choices=ATTRACTORS, help="Load with a builtin attractor"
    )
    parser.add_argument("--preset", help="Load a saved preset system")
    parser.add_argument("--mode", choices=ANALYSIS_MODES, help="Run analysis mode")
    parser.add_argument(
        "--theme",
        choices=("system", "light", "dark"),
        help="Set the theme for plot/view widgets",
    )
    args = parser.parse_args()

    # needs to go before constructing the window
    if args.reset:
        session_store.clear(session_store.app_settings())

    app = pg.mkQApp()
    # set the app name strange-attractors for now so the standard path writable location
    # doesn't need to be changed
    app.setApplicationName("strange-attractors")
    app.setStyle("Fusion")
    w = Window()
    w.showFullScreen() if args.fullscreen else w.show()

    actions = {
        "explore": lambda: w.set_workspace_mode("explore"),
        "system": lambda: w.set_workspace_mode("system"),
        "default": w.restore_default_layout,
        "attractor": lambda: w.controls.dropdown.setCurrentText(args.attractor),
        "preset": lambda: w.load_preset(args.preset),
        "mode": lambda: w.open_panel_dock(ANALYSIS_MODES[args.mode]),
        "theme": lambda: w.set_theme(None if args.theme == "system" else args.theme),
    }

    for name, func in actions.items():
        if getattr(args, name):
            func()

    capture_output = CaptureOutput(w.output_panel)
    capture_output.install()

    configure_perf_logging()

    if session_store.app_settings().value("startup/show_welcome", True, bool):
        QtCore.QTimer.singleShot(0, w.show_welcome)

    pg.exec()


if __name__ == "__main__":
    main()
