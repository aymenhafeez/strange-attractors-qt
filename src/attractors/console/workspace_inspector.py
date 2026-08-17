import pandas as pd

HELP_ROWS = [
    ("views", "plots.new(name=None)", "Create or activate a 2D plot dock"),
    ("views", "views3d.new(name=None)", "Create or activate a 3D view dock"),
    ("views", "current_plot()", "Return the active 2D plot"),
    ("views", "current_view3d()", "Return the active 3D view"),
    (
        "2D plotting",
        "plot.line(x, y, mode='replace')",
        "Draw a line in the default plot",
    ),
    (
        "2D plotting",
        "plot.scatter(x, y, mode='replace')",
        "Draw points in the default plot",
    ),
    (
        "2D plotting",
        "p.explore.slider(name, value, start, end, step)",
        "Add a plot-local slider",
    ),
    ("2D plotting", "p.explore.curve(name, x, y)", "Add a reactive line trace"),
    ("2D plotting", "p.explore.scatter(name, x, y)", "Add a reactive scatter trace"),
    (
        "2D plotting",
        "p.explore.hist(name, values, bins=50)",
        "Add a reactive histogram",
    ),
    (
        "2D plotting",
        "p.explore.vline(name, x)",
        "Add a reactive vertical reference line",
    ),
    (
        "2D plotting",
        "p.explore.hline(name, y)",
        "Add a reactive horizontal reference line",
    ),
    ("3D plotting", "v.line3d(points, mode='replace')", "Draw a 3D line"),
    ("3D plotting", "v.scatter3d(points, mode='replace')", "Draw 3D points"),
    (
        "3D plotting",
        "v.explore.slider(name, value, start, end, step)",
        "Add a view-local slider",
    ),
    ("3D plotting", "v.explore.line3d(name, points)", "Add a reactive 3D line trace"),
    (
        "3D plotting",
        "v.explore.scatter3d(name, points)",
        "Add a reactive 3D scatter trace",
    ),
    ("3D view", "v.fit()", "Fit the 3D camera to visible data"),
    ("3D view", "v.reset_camera()", "Reset the 3D camera"),
    ("3D view", "v.grid(visible=True)", "Show or hide the 3D grid"),
    (
        "colours",
        "colourmap(values, cmap='viridis')",
        "Map scalar values to RGBA colours",
    ),
]


class WorkspaceInspector:
    def __init__(self, console_panel):
        self._console_panel = console_panel

    def __repr__(self):
        plots = len(self._console_panel.names())
        views3d = len(self._console_panel.views3d.names())

        return f"ExploreInspector(plots={plots}, views3d={views3d})"

    def help(self):
        return pd.DataFrame(HELP_ROWS, columns=["category", "command", "description"])

    def summary(self):
        items = self._console_panel.workspace_view_items()
        active_kind, active_name = self._console_panel.active_view_key()

        return pd.Series(
            {
                "active_kind": active_kind,
                "active_name": active_name,
                "plots": len(self._console_panel.plots.names()),
                "views3d": len(self._console_panel.views3d.names()),
                "workspace_items": len(items),
            }
        )

    def views(self):
        rows = []
        active_key = self._console_panel.active_view_key()

        for item in self._console_panel.workspace_view_items():
            key = (item["kind"], item["name"])
            view = (
                self._console_panel.plots.get(item["name"], activate=False)
                if item["kind"] == "plot"
                else self._console_panel.views3d.get(item["name"], activate=False)
            )

            rows.append(
                {
                    "kind": item["kind"],
                    "name": item["name"],
                    "label": item["label"],
                    "active": key == active_key,
                    "sliders": len(view.explore.slider_names()),
                    "traces": len(view.explore.trace_names()),
                }
            )

        return pd.DataFrame(rows)
