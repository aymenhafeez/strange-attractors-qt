from pyqtgraph.Qt import QtCore

LAYOUT_VERSION = 2
MODES = ("viewport", "system", "explore")


class WorkspaceLayouts(QtCore.QObject):
    def __init__(self, window, registry):
        super().__init__(window)
        self.window = window
        self.registry = registry
        self.current = None
        self.states = {}
        self.known_ids = {}

    def capture_current(self):
        if self.current is not None:
            self.states[self.current] = self.window.saveState(LAYOUT_VERSION)
            self.known_ids[self.current] = set(self.registry)

    def switch(self, mode, *, reset=False):
        if mode not in MODES:
            raise ValueError(f"Unknown workspace mode {mode}")
        if mode == self.current and not reset:
            return

        self.capture_current()

        with self.registry.presentation_change():
            state = None if reset else self.states.get(mode)
            restored = state is not None and self.window.restoreState(
                state, LAYOUT_VERSION
            )
            if restored:
                known = self.known_ids.get(mode, set())
                for key in self.registry:
                    if key not in known:
                        self.registry.hide(key)
            else:
                self.build_default(mode)

        self.current = mode
        self.capture_current()

    def build_default(self, mode):
        window, d = self.window, self.registry
        area, axis = QtCore.Qt.DockWidgetArea, QtCore.Qt.Orientation
        for dock in d.values():
            dock.setFloating(False)
            window.removeDockWidget(dock)
            dock.hide()

        def place(key, side):
            window.addDockWidget(side, d[key])

        place("viewport", area.RightDockWidgetArea)
        place(
            "script",
            area.RightDockWidgetArea if mode == "explore" else area.LeftDockWidgetArea,
        )
        place("plot.default", area.RightDockWidgetArea)
        window.splitDockWidget(
            d["script"] if mode == "explore" else d["viewport"],
            d["plot.default"],
            axis.Horizontal,
        )

        place("parameters", area.LeftDockWidgetArea)
        place("data", area.LeftDockWidgetArea)
        window.splitDockWidget(d["parameters"], d["data"], axis.Vertical)
        if mode != "explore":
            window.splitDockWidget(d["data"], d["script"], axis.Vertical)
        place("view_options", area.LeftDockWidgetArea)
        window.tabifyDockWidget(d["parameters"], d["view_options"])

        place("trajectories", area.RightDockWidgetArea)
        window.splitDockWidget(d["plot.default"], d["trajectories"], axis.Horizontal)
        place("presets", area.RightDockWidgetArea)
        window.splitDockWidget(d["trajectories"], d["presets"], axis.Vertical)
        place("custom", area.RightDockWidgetArea)
        window.tabifyDockWidget(d["presets"], d["custom"])

        place("projection_panel", area.RightDockWidgetArea)
        window.splitDockWidget(d["viewport"], d["projection_panel"], axis.Vertical)
        for key in ("poincare_panel", "lyapunov_panel", "bifurcation_panel"):
            place(key, area.RightDockWidgetArea)
            window.tabifyDockWidget(d["projection_panel"], d[key])
        for key in ("view3d.default", "table.default"):
            place(key, area.RightDockWidgetArea)
            window.tabifyDockWidget(d["plot.default"], d[key])

        place("console", area.BottomDockWidgetArea)
        place("output", area.BottomDockWidgetArea)
        window.tabifyDockWidget(d["console"], d["output"])

        static = {
            "viewport",
            "script",
            "console",
            "output",
            "parameters",
            "view_options",
            "data",
            "trajectories",
            "presets",
            "custom",
            "projection_panel",
            "poincare_panel",
            "lyapunov_panel",
            "bifurcation_panel",
            "plot.default",
            "view3d.default",
            "table.default",
        }
        for key, dock in d.items():
            if key not in static:
                window.addDockWidget(area.RightDockWidgetArea, dock)
                default_id = key.split(".", 1)[0] + ".default"
                window.tabifyDockWidget(d[default_id], dock)

        opened = set()
        if mode in {"viewport", "system"}:
            opened.update(
                (
                    "viewport",
                    "parameters",
                    "view_options",
                    "data",
                    "trajectories",
                    "presets",
                    "custom",
                )
            )
        if mode in {"system", "explore"}:
            opened.update(("script", "console", "plot.default"))
        for key in opened:
            d.show(key, activate=False)
        for key in ("parameters", "presets", "plot.default", "console"):
            if key in opened:
                d[key].raise_()
        window.layout().activate()
        if mode == "explore":
            window.resizeDocks(
                [d["script"], d["plot.default"]], [440, 660], axis.Horizontal
            )
        else:
            window.resizeDocks(
                [d["parameters"], d["viewport"], d["trajectories"]],
                [240, 600, 260],
                axis.Horizontal,
            )
        if "console" in opened:
            window.resizeDocks([d["console"]], [180], axis.Vertical)
