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

    def _on_follow_requested(self, kind, options):
        plot_options = dict(options)
        live = bool(plot_options.pop("live", True))
        plot = plot_options.pop("plot", None)
        # if live and kind in LIVE_KINDS:
        if live and kind in {*PREVIEW}:
            self._set_follow(kind, plot=plot, **plot_options)
        else:
            self._run_console_plot_request(kind, plot=plot, **plot_options)

    def _run_console_plot_request(self, kind, *, plot=None, **options):
        plot_name = self._follow_plot_name(plot)
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
        if kind in {"returns", "return_lags"}:
            plotter = (
                self.window.system.plot_returns
                if kind == "returns"
                else self.window.system.plot_return_lags
            )
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

