import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore

from .system import PLOT_MODE_OVERLAY, PLOT_MODE_REPLACE

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


def _plot_mode(mode=PLOT_MODE_REPLACE):
    normalised = mode.strip().lower()
    if normalised == PLOT_MODE_REPLACE:
        return PLOT_MODE_REPLACE
    if normalised == PLOT_MODE_OVERLAY:
        return PLOT_MODE_OVERLAY

    raise ValueError("Plot mode must be 'replace' or 'overlay'")


class LivePlotController:
    def __init__(self, window):
        self.window = window

    @property
    def live_plots(self):
        return self.window._live_plots

    @live_plots.setter
    def live_plots(self, value):
        self.window._live_plots = value

    @property
    def live_items(self):
        return self.window._live_items

    @live_items.setter
    def live_items(self, value):
        self.window._live_items = value

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

    def _sync_plots(self):
        window_state = vars(self.window)
        combo = window_state.get("toolbar_live_plot_combo")
        name_edit = window_state.get("toolbar_live_plot_name")
        if combo is None or name_edit is None:
            return

        names = self.window.jupyter_console_panel.plots.names()
        current_name = self.window.jupyter_console_panel.plots.current_name
        with QtCore.QSignalBlocker(combo):
            combo.clear()
            for name in names:
                combo.addItem(self._plot_combo_label(name), name)
                combo.setItemData(
                    combo.count() - 1,
                    self._plot_combo_tooltip(name),
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                )
            current_index = names.index(current_name) if current_name in names else -1
            if current_index >= 0:
                combo.setCurrentIndex(current_index)
        name_edit.setText(current_name if current_name in names else "")
        self.window.workspace_panel.set_plots(names, current_name)
        self._sync_live_menu(current_name)

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

    def _live_trace_mode(self, spec):
        if spec.get("kind") in PREVIEW:
            return "live preview"

        return "full solve"

    def _on_toolbar_plot_selected(self):
        combo = self.window.toolbar_live_plot_combo
        plot_name = combo.currentData()
        if plot_name is None:
            plot_name = combo.currentText()
        plot_name = str(plot_name).strip()
        if not plot_name:
            return

        self.window.toolbar_live_plot_name.setText(plot_name)
        self.window.jupyter_console_panel.plots.get(plot_name)

    def _on_plot_requested(self, kind, options):
        plot_options = dict(options)
        live = bool(plot_options.pop("live", True))
        plot = plot_options.pop("plot", None)
        # if live and kind in LIVE_KINDS:
        if live and kind in {*PREVIEW}:
            self._register_live_plot(kind, plot=plot, **plot_options)
        else:
            self._run_console_plot_request(kind, plot=plot, **plot_options)

    def _run_console_plot_request(self, kind, *, plot=None, **options):
        plot_name = self._plot_name(plot)
        target = self._live_plot_target(plot_name)
        mode = _plot_mode(options.pop("mode", PLOT_MODE_REPLACE))
        label = options.pop("label", None)

        if mode == PLOT_MODE_REPLACE:
            self.live_plots.pop(plot_name, None)
            self._clear_live_items(plot_name)

        plotter, args, kwargs, accepts_label = self._console_plot_call(kind, options)
        if accepts_label:
            kwargs["label"] = label
        plotter(*args, plot=target, mode=mode, **kwargs)

        self.window.workspace_panel.set_status(f"Ran {kind} plot")
        self._sync_plots()

    def _console_plot_call(self, kind, options):
        if kind == "axis":
            return (
                self.window.system.plot_axis,
                (options.get("axis", "x"),),
                {"trajectory": options.get("trajectory", 0)},
                True,
            )
        if kind in TIMESERIES:
            return (
                self._plot_derived_timeseries,
                (kind,),
                {"trajectory": options.get("trajectory", 0)},
                True,
            )
        if kind == "projection":
            return (
                self.window.system.plot_projection,
                (options.get("x_axis", "x"), options.get("y_axis", "y")),
                {"trajectory": options.get("trajectory", 0)},
                True,
            )
        if kind == "separation":
            return (
                self.window.system.plot_separation,
                (options.get("a", 0), options.get("b", 1)),
                {"log": options.get("log", False)},
                True,
            )
        if kind == "separation_fit":
            return (
                self.window.system.plot_separation_fit,
                (options.get("a", 0), options.get("b", 1)),
                {
                    "t_min": options.get("t_min"),
                    "t_max": options.get("t_max"),
                    "step_min": options.get("step_min"),
                    "step_max": options.get("step_max"),
                },
                True,
            )
        if kind == "crossings":
            return (
                self.window.system.plot_crossings,
                (options.get("axis", "z"),),
                {
                    "value": options.get("value"),
                    "direction": options.get("direction", "both"),
                    "trajectory": options.get("trajectory", 0),
                },
                False,
            )

        raise ValueError(f"Unknown console plot kind: {kind}")

    def _on_plots_changed(self):
        names = set(self.window.jupyter_console_panel.plots.names())
        live_plots = self.live_plots
        for name in list(live_plots):
            if name not in names:
                live_plots.pop(name, None)
                self._clear_live_items(name)
        self._sync_plots()

    def _clear_plot(self):
        plot_name = self.window.jupyter_console_panel.plots.current_name
        self.window.jupyter_console_panel.plots.clear()
        self._clear_live_items(plot_name)

    def _clear_all_plots(self):
        self.window.jupyter_console_panel.plots.clear_all()
        self.live_plots.clear()
        self.live_items.clear()
        self.window.workspace_panel.set_status("Cleared live plots")
        self._sync_live_menu()

    def _close_plot(self):
        plot_name = self.window.jupyter_console_panel.plots.current_name
        self.window.jupyter_console_panel.plots.close()
        self.live_plots.pop(plot_name, None)
        self._clear_live_items(plot_name)
        self._sync_live_menu()

    def _register_live_plot(
        self, kind, *, plot=None, mode=PLOT_MODE_REPLACE, **options
    ):
        plot_name = self._plot_name(plot)
        mode = _plot_mode(mode)
        spec = {
            "source": "main",
            "kind": kind,
            "plot": plot_name,
            "mode": mode,
            **options,
        }
        specs = self.live_plots.setdefault(plot_name, [])
        if mode == PLOT_MODE_OVERLAY:
            specs.append(spec)
        else:
            self.live_plots[plot_name] = [spec]
            self._clear_live_items(plot_name)
        self._refresh_live_plot(plot_name)
        self._sync_plots()
        return pd.Series(spec)

    def _plot_name(self, plot):
        plots = self.window.jupyter_console_panel.plots
        if plot is None:
            return plots.current_name

        plot_name = str(plot).strip()
        if not plot_name:
            raise ValueError("Plot name cannot be empty")
        if plot_name not in plots.names():
            plots.new(plot_name)
        else:
            plots.get(plot_name)

        return plot_name

    def _clear_live_items(self, plot_name):
        live_items = self.live_items
        plot_key = str(plot_name)
        for key in list(live_items):
            if key[0] == plot_key:
                live_items.pop(key, None)

    def _refresh_live_plot(self, plot_name):
        specs = self.live_plots.get(plot_name, [])
        try:
            for index, spec in enumerate(specs):
                self._plot_live_spec(spec, trace_index=index)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            self.window.workspace_panel.set_status(str(exc))
            return

        self.window.workspace_panel.set_status(self._live_status_text())

    def _plot_live_spec(self, spec, *, trace_index):
        kind = spec["kind"]
        plot = spec["plot"]
        target = self._live_plot_target(plot)
        key = self._live_item_key(plot, trace_index)
        live_items = self.live_items
        if self._update_live_item(
            plot,
            trace_index,
            spec,
            target=target,
        ):
            return

        mode = PLOT_MODE_REPLACE if trace_index == 0 else PLOT_MODE_OVERLAY
        pen = spec.get("pen")
        label = spec.get("label") or self._live_trace_label(spec)
        if kind == "axis":
            item = self.window.system.plot_axis(
                spec["axis"],
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
            live_items[key] = item
            return

        if kind in TIMESERIES:
            item = self._plot_derived_timeseries(
                kind,
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
            live_items[key] = item
            return

        if kind == "projection":
            item = self.window.system.plot_projection(
                spec.get("x_axis", "x"),
                spec.get("y_axis", "y"),
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
            )
            live_items[key] = item
            return

        if kind == "separation":
            item = self.window.system.plot_separation(
                spec.get("a", 0),
                spec.get("b", 1),
                log=spec.get("log", False),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
            live_items[key] = item
            return

        if kind == "separation_fit":
            items = self._plot_live_separation_fit(
                spec,
                target,
                mode=mode,
                pen=pen,
                label=label,
            )
            live_items[key] = items
            return

        if kind == "vector_field":
            item = self.window.system.plot_vector_field(
                spec.get("x_axis", "x"),
                spec.get("y_axis", "y"),
                fixed_axis=spec.get("fixed_axis"),
                fixed_value=spec.get("fixed_value", 0.0),
                x_range=spec.get("x_range"),
                y_range=spec.get("y_range"),
                density=spec.get("density", 21),
                plot=target,
                mode=mode,
                pen=pen,
                scale=spec.get("scale", 0.75),
                colour_by_speed=spec.get("colour_by_speed", False),
                speed_bands=spec.get("speed_bands", 5),
            )
            live_items[key] = item
            return

        raise ValueError(f"Unknown live plot kind: {kind}")

            return (
                plotter,
                (),
                {
                    "trajectory": options.get("trajectory", 0),
                    "samples": options.get("samples", 2000),
                    "min_lag": options.get("min_lag", 50),
                    "count": options.get("count", 20),
                    "unique": options.get("unique", True),
                },
                False,
            )

        raise ValueError(f"Unknown console plot kind: {kind}")

