from pyqtgraph.Qt import QtCore

PREVIEW = {
    "axis",
    "displacement",
    "projection",
    "radius",
    "separation",
    "separation_fit",
    "speed",
    "vector_field",
}
TIMESERIES = {"displacement", "radius", "speed"}


class LivePlotController:
    def __init__(self, window):
        self.window = window
        self.live_plots = {}
        self.live_items = {}

    def _rename_plot(self, old_name, new_name):
        live_specs = self.live_plots.get(old_name)
        try:
            self.window.jupyter_console_panel.plots.rename(old_name, new_name)
        except (KeyError, ValueError) as exc:
            self.window.workspace_panel.set_status(str(exc))
            return

        if live_specs is not None:
            self.live_plots.pop(old_name, None)
            renamed_specs = []
            for spec in live_specs:
                renamed_spec = dict(spec)
                renamed_spec["plot"] = new_name
                renamed_specs.append(renamed_spec)
            self.live_plots[new_name] = renamed_specs
            self._rename_live_items(old_name, new_name)

    def _plot_combo_label(self, plot_name):
        count = len(self.live_plots.get(plot_name, []))
        if count == 0:
            return str(plot_name)

        return f"{plot_name} ({count})"

    def _plot_combo_tooltip(self, plot_name):
        count = len(self.live_plots.get(plot_name, []))
        if count == 0:
            return f"{plot_name}: no live traces"
        if count == 1:
            return f"{plot_name}: 1 live trace"

        return f"{plot_name}: {count} live traces"

    def _sync_live_menu(self, plot_name=None):
        if plot_name is None:
            plot_name = self.window.jupyter_console_panel.plots.current_name

        plot_name = str(plot_name).strip()
        specs = self.live_plots.get(plot_name, [])

        traces = [
            {
                "index": index,
                "label": self._live_trace_label(spec),
                "mode": self._live_trace_mode(spec),
            }
            for index, spec in enumerate(specs)
        ]

        self.window.workspace_panel.set_live_traces(plot_name, traces)

    def _live_trace_label(self, spec):
        label = spec.get("label")
        if label:
            return str(label)

        kind = spec.get("kind")
        trajectory = spec.get("trajectory", 0)
        trajectory_label = f"T{trajectory}"

        if kind == "axis":
            return f"{trajectory_label} {spec.get('axis', 'axis')}"
        if kind in TIMESERIES:
            return f"{trajectory_label} {kind}"
        if kind == "projection":
            return (
                f"{trajectory_label} "
                f"{spec.get('x_axis', 'x')}-{spec.get('y_axis', 'y')}"
            )
        if kind == "separation":
            prefix = "log sep" if spec.get("log", False) else "sep"
            return f"T{spec.get('a', 0)}-T{spec.get('b', 1)} {prefix}"
        if kind == "separation_fit":
            return f"T{spec.get('a', 0)}-T{spec.get('b', 1)} sep fit"
        if kind == "vector_field":
            return (
                f"{spec.get('x_axis', 'x')}-{spec.get('y_axis', 'y')} field "
                f"{spec.get('fixed_axis', 'z')}={spec.get('fixed_value', 0.0):g}"
            )

        return str(kind or "trace")
