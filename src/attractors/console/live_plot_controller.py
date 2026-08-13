import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore

from .system import PLOT_MODE_OVERLAY, PLOT_MODE_REPLACE

PREVIEW_UPDATE_INTERVAL = 120  # ms
AXES = {"x": 0, "y": 1, "z": 2}
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
AUTO_PENS = ["w", "r", "g", "b", "c", "m", "y"]


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
        self._auto_pen_indices = {}

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
        auto_pen_index = self._auto_pen_indices.get(old_name)
        try:
            self.window.jupyter_console_panel.plots.rename(old_name, new_name)
        except (KeyError, ValueError) as exc:
            self.window.system_toolbar.set_status(str(exc))
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
        if auto_pen_index is not None:
            self._auto_pen_indices.pop(old_name, None)
            self._auto_pen_indices[new_name] = auto_pen_index

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
        self.window.system_toolbar.set_plots(names, current_name)
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
        self.window.system_toolbar.set_live_traces(plot_name, traces)

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

    def _auto_pen(self, plot_name, mode):
        if mode == PLOT_MODE_OVERLAY:
            index = self._auto_pen_indices.get(plot_name, 0)
        else:
            index = 0
        pen = AUTO_PENS[index % len(AUTO_PENS)]
        self._auto_pen_indices[plot_name] = index + 1

        return pen

    def _plot_pen(self, plot_name, mode, pen):
        if pen is None:
            return self._auto_pen(plot_name, mode)

        if mode != PLOT_MODE_OVERLAY:
            self._auto_pen_indices[plot_name] = 0

        return pen

    def _run_console_plot_request(self, kind, *, plot=None, **options):
        plot_name = self._plot_name(plot)
        target = self._live_plot_target(plot_name)
        mode = _plot_mode(options.pop("mode", PLOT_MODE_REPLACE))
        label = options.pop("label", None)
        pen = self._plot_pen(plot_name, mode, options.pop("pen", None))

        if mode == PLOT_MODE_REPLACE:
            self.live_plots.pop(plot_name, None)
            self._clear_live_items(plot_name)

        plotter, args, kwargs, accepts_label = self._console_plot_call(kind, options)
        if accepts_label:
            kwargs["label"] = label
        if pen is not None:
            kwargs["pen"] = pen
        plotter(*args, plot=target, mode=mode, **kwargs)

        self.window.system_toolbar.set_status(f"Ran {kind} plot")
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
                self._auto_pen_indices.pop(name, None)
        self._sync_plots()

    def _clear_plot(self):
        plot_name = self.window.jupyter_console_panel.plots.current_name
        self.window.jupyter_console_panel.plots.clear()
        self.live_plots.pop(plot_name, None)
        self._clear_live_items(plot_name)
        self._auto_pen_indices.pop(plot_name, None)
        self.window.system_toolbar.set_status(self._live_status_text())
        self._sync_live_menu(plot_name)

    def _clear_all_plots(self):
        self.window.jupyter_console_panel.plots.clear_all()
        self.live_plots.clear()
        self.live_items.clear()
        self._auto_pen_indices.clear()
        self.window.system_toolbar.set_status("Cleared live plots")
        self._sync_live_menu()

    def _close_plot(self):
        plot_name = self.window.jupyter_console_panel.plots.current_name
        self.window.jupyter_console_panel.plots.close()
        self.live_plots.pop(plot_name, None)
        self._clear_live_items(plot_name)
        self._auto_pen_indices.pop(plot_name, None)
        self._sync_live_menu()

    def _register_live_plot(
        self, kind, *, plot=None, mode=PLOT_MODE_REPLACE, **options
    ):
        plot_name = self._plot_name(plot)
        mode = _plot_mode(mode)
        pen = self._plot_pen(plot_name, mode, options.pop("pen", None))
        spec = {
            "source": "main",
            "kind": kind,
            "plot": plot_name,
            "mode": mode,
            "pen": pen,
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

    def _live_plot_frame(self):
        rows = []
        for specs in self.live_plots.values():
            for index, spec in enumerate(specs):
                row = dict(spec)
                row["trace"] = index
                rows.append(row)

        columns = [
            "plot",
            "trace",
            "source",
            "kind",
            "mode",
            "axis",
            "x_axis",
            "y_axis",
            "fixed_axis",
            "fixed_value",
            "x_range",
            "y_range",
            "density",
            "scale",
            "colour_by_speed",
            "speed_bands",
            "trajectory",
            "a",
            "b",
            "log",
            "pen",
            "fit_pen",
            "label",
            "zoom_region",
            "t_min",
            "t_max",
            "step_min",
            "step_max",
        ]

        if not rows:
            return pd.DataFrame(columns=columns).set_index("plot")

        return pd.DataFrame(rows).reindex(columns=columns).set_index("plot")

    def _clear_live_plot(self, plot=None):
        live_plots = self.live_plots

        if plot is None:
            plot_name = self.window.jupyter_console_panel.plots.current_name
        else:
            plot_name = str(plot).strip()

        if not plot_name:
            raise ValueError("Plot name cannot be empty")

        live_plots.pop(plot_name, None)
        self._clear_live_items(plot_name)
        self._auto_pen_indices.pop(plot_name, None)
        self._live_plot_target(plot_name).clear()
        self.window.system_toolbar.set_status(self._live_status_text())
        self._sync_live_menu(plot_name)

        return self._live_plot_frame()

    def _remove_live_trace(self, plot_name, trace_index):
        plot_name = str(plot_name).strip()
        if not plot_name:
            return self._live_plot_frame()

        live_plots = self.live_plots
        specs = live_plots.get(plot_name, [])

        if not 0 <= int(trace_index) < len(specs):
            return self._live_plot_frame()

        specs.pop(int(trace_index))
        target = self._live_plot_target(plot_name)
        target.clear()

        self._clear_live_items(plot_name)

        if specs:
            self._refresh_live_plot(plot_name)
        else:
            live_plots.pop(plot_name, None)
            self.window.system_toolbar.set_status(self._live_status_text())

        self._sync_live_menu(plot_name)

        return self._live_plot_frame()

    def _clear_all_live_plots(self):
        self.live_plots.clear()
        self.live_items.clear()
        self._auto_pen_indices.clear()
        self.window.system_toolbar.set_status("No live plots")
        self._sync_live_menu()

        return self._live_plot_frame()

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

    def _live_plot_target(self, plot_name):
        plots = self.window.jupyter_console_panel.plots
        try:
            return plots.get(plot_name, activate=False)
        except KeyError:
            return plots.new(plot_name, activate=False)

    def _live_item_key(self, plot_name, trace_index):
        return (str(plot_name), int(trace_index))

    def _clear_live_items(self, plot_name):
        live_items = self.live_items
        plot_key = str(plot_name)
        for key in list(live_items):
            if key[0] == plot_key:
                live_items.pop(key, None)

    def _rename_live_items(self, old_name, new_name):
        live_items = self.live_items
        old_key = str(old_name)
        new_key = str(new_name)
        renamed = {}

        for key, item in list(live_items.items()):
            if key[0] != old_key:
                continue
            renamed[(new_key, key[1])] = item
            live_items.pop(key, None)
        live_items.update(renamed)

    def _refresh_live_plot(self, plot_name):
        specs = self.live_plots.get(plot_name, [])
        try:
            for index, spec in enumerate(specs):
                self._plot_live_spec(spec, trace_index=index)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            self.window.system_toolbar.set_status(str(exc))
            return

        self.window.system_toolbar.set_status(self._live_status_text())

    def _refresh_live_preview(self, solutions=None, *, kinds=None):
        live_plots = self.live_plots
        live_items = self.live_items
        if not live_plots or not live_items:
            return

        preview_kinds = PREVIEW if kinds is None else set(kinds)
        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        last_update = self.window._last_live_preview_update
        if (
            solutions is None
            and last_update is not None
            and now_ms - last_update < PREVIEW_UPDATE_INTERVAL
        ):
            return

        refreshed = False
        for plot_name, specs in list(live_plots.items()):
            for index, spec in enumerate(specs):
                if spec.get("kind") not in preview_kinds:
                    continue
                if self._update_live_item(
                    plot_name,
                    index,
                    spec,
                    solutions=solutions,
                ):
                    refreshed = True

        if refreshed:
            self.window._last_live_preview_update = now_ms

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

    def _plot_derived_timeseries(
        self,
        kind,
        *,
        trajectory,
        plot,
        mode,
        pen=None,
        label=None,
        zoom_region=False,
    ):
        kwargs = {
            "trajectory": trajectory,
            "plot": plot,
            "mode": mode,
            "label": label,
            "zoom_region": zoom_region,
        }
        if pen is not None:
            kwargs["pen"] = pen

        if kind == "displacement":
            return self.window.system.plot_displacement(**kwargs)
        if kind == "radius":
            return self.window.system.plot_radius(**kwargs)
        if kind == "speed":
            return self.window.system.plot_speed(**kwargs)

        raise ValueError(f"Unknown derived plot kind: {kind}")

    def _plot_live_separation_fit(self, spec, target, *, mode, pen, label):
        data = self._live_separation_fit_data(spec)

        separation_kwargs = {}
        if pen is not None:
            separation_kwargs["pen"] = pen
        if label is not None:
            separation_kwargs["name"] = str(label)

        fit_pen = spec.get("fit_pen", pen)
        fit_label = f"{label} fit" if label else None
        fit_kwargs = {}
        if fit_pen is not None:
            fit_kwargs["pen"] = fit_pen
        if fit_label is not None:
            fit_kwargs["name"] = fit_label

        separation_item = target.line(
            data["separation_t"],
            data["log_distance"],
            mode=mode,
            bottom="t",
            left=data["axis_label"],
            **separation_kwargs,
        )
        fit_item = target.line(
            data["fit_t"],
            data["fit_y"],
            mode=PLOT_MODE_OVERLAY,
            bottom="t",
            left=data["axis_label"],
            **fit_kwargs,
        )

        return separation_item, fit_item

    def _update_live_item(
        self,
        plot_name,
        trace_index,
        spec,
        *,
        target=None,
        solutions=None,
    ):
        key = self._live_item_key(plot_name, trace_index)
        item = self.live_items.get(key)
        if item is None:
            return False

        if target is None:
            try:
                target = self.window.jupyter_console_panel.plots.get(
                    plot_name, activate=False
                )
            except KeyError:
                return False
        if isinstance(item, tuple):
            if not all(target.has_item(part) for part in item):
                return False
        elif not target.has_item(item):
            return False

        if spec.get("kind") == "separation_fit":
            separation_item, fit_item = item
            data = self._live_separation_fit_data(spec, solutions=solutions)
            separation_item.setData(data["separation_t"], data["log_distance"])
            fit_item.setData(data["fit_t"], data["fit_y"])
            target.set_labels(bottom="t", left=data["axis_label"])
        elif spec.get("kind") == "vector_field":
            data = self._live_vector_field_data(spec)
            if isinstance(item, tuple):
                segments = data.get("segments")
                if segments is None or len(item) != len(segments):
                    return False
                for part, (x_data, y_data, _pen) in zip(item, segments):
                    part.setData(x_data, y_data)
            else:
                item.setData(data["x"], data["y"])
            target.set_labels(bottom=data["bottom"], left=data["left"])
        else:
            x_data, y_data, bottom, left = self._live_trace_data(
                spec,
                solutions=solutions,
            )
            item.setData(x_data, y_data)
            target.set_labels(bottom=bottom, left=left)

        return True

    def _live_trace_data(self, spec, *, solutions=None):
        kind = spec["kind"]
        if kind == "axis":
            axis = str(spec["axis"]).lower()
            trajectory = spec.get("trajectory", 0)
            solution = self._live_solution(trajectory, solutions)
            return (
                self._live_time(trajectory, solution),
                solution[:, AXES[axis]],
                "t",
                axis,
            )

        if kind in TIMESERIES:
            trajectory = spec.get("trajectory", 0)
            solution = self._live_solution(trajectory, solutions)
            times = self._live_time(trajectory, solution)
            return (
                times,
                self._live_derived_values(kind, solution, times),
                "t",
                kind,
            )

        if kind == "projection":
            x_axis = str(spec.get("x_axis", "x")).lower()
            y_axis = str(spec.get("y_axis", "y")).lower()
            trajectory = spec.get("trajectory", 0)
            solution = self._live_solution(trajectory, solutions)
            return (
                solution[:, AXES[x_axis]],
                solution[:, AXES[y_axis]],
                str(spec.get("x_axis", "x")),
                str(spec.get("y_axis", "y")),
            )

        if kind == "separation":
            a = spec.get("a", 0)
            b = spec.get("b", 1)
            log = spec.get("log", False)
            value_column = "log_distance" if log else "distance"
            axis_label = f"log separation {a}-{b}" if log else f"separation {a}-{b}"
            if solutions is not None:
                sol_a = self._live_solution(a, solutions)
                sol_b = self._live_solution(b, solutions)
                length = min(len(sol_a), len(sol_b))
                distance = np.linalg.norm(sol_a[:length] - sol_b[:length], axis=1)
                if log:
                    with np.errstate(divide="ignore"):
                        distance = np.log(distance)
                return (
                    self._live_time(a, sol_a)[:length],
                    distance,
                    "t",
                    axis_label,
                )

            frame = self.window.system.separation(a, b, log=log)
            return (
                frame["t"].to_numpy(),
                frame[value_column].to_numpy(),
                "t",
                axis_label,
            )

        raise ValueError(f"Unknown live plot kind: {kind}")

    @staticmethod
    def _live_derived_values(kind, solution, times):
        if kind == "radius":
            return np.linalg.norm(solution, axis=1)
        if kind == "displacement":
            if len(solution) == 0:
                return np.array([], dtype=np.float64)
            return np.linalg.norm(solution - solution[0], axis=1)
        if kind == "speed":
            if len(solution) < 2:
                return np.zeros(len(solution), dtype=np.float64)

            velocity = np.gradient(solution, times, axis=0)
            return np.linalg.norm(velocity, axis=1)

        raise ValueError(f"Unknown derived plot kind: {kind}")

    def _live_vector_field_data(self, spec):
        x_axis = str(spec.get("x_axis", "x")).lower()
        y_axis = str(spec.get("y_axis", "y")).lower()
        frame = self.window.system.vector_field_slice(
            x_axis,
            y_axis,
            fixed_axis=spec.get("fixed_axis"),
            fixed_value=spec.get("fixed_value", 0.0),
            x_range=spec.get("x_range"),
            y_range=spec.get("y_range"),
            density=spec.get("density", 21),
        )
        if spec.get("colour_by_speed", False):
            return {
                "segments": self.window.system._vector_field_speed_bands(
                    frame,
                    x_axis,
                    y_axis,
                    spec.get("scale", 0.75),
                    spec.get("speed_bands", 5),
                ),
                "bottom": x_axis,
                "left": y_axis,
            }

        x_data, y_data = self.window.system._vector_field_segments(
            frame,
            x_axis,
            y_axis,
            spec.get("scale", 0.75),
        )

        return {"x": x_data, "y": y_data, "bottom": x_axis, "left": y_axis}

    def _live_separation_fit_data(self, spec, *, solutions=None):
        a = spec.get("a", 0)
        b = spec.get("b", 1)
        frame = self._live_separation_frame(
            a,
            b,
            log=True,
            solutions=solutions,
        )

        mask = np.isfinite(frame["log_distance"].to_numpy())

        if spec.get("t_min") is not None:
            mask &= frame["t"].to_numpy() >= spec["t_min"]
        if spec.get("t_max") is not None:
            mask &= frame["t"].to_numpy() <= spec["t_max"]
        if spec.get("step_min") is not None:
            mask &= frame["step"].to_numpy() >= spec["step_min"]
        if spec.get("step_max") is not None:
            mask &= frame["step"].to_numpy() <= spec["step_max"]

        fit_frame = frame.loc[mask].reset_index(drop=True)
        if len(fit_frame) < 2:
            raise ValueError("At least two finite log-separation points are required")

        fit = self.window.system._fit_log_separation(fit_frame)
        fit_t = fit_frame["t"].to_numpy()
        fit_y = fit["slope"] * fit_t + fit["intercept"]
        axis_label = f"log separation fit {a}-{b}"

        return {
            "separation_t": frame["t"].to_numpy(),
            "log_distance": frame["log_distance"].to_numpy(),
            "fit_t": fit_t,
            "fit_y": fit_y,
            "axis_label": axis_label,
        }

    def _live_separation_frame(self, a, b, *, log, solutions=None):
        if solutions is None:
            return self.window.system.separation(a, b, log=log)

        sol_a = self._live_solution(a, solutions)
        sol_b = self._live_solution(b, solutions)
        length = min(len(sol_a), len(sol_b))
        distance = np.linalg.norm(sol_a[:length] - sol_b[:length], axis=1)
        columns = {
            "trajectory_a": a,
            "trajectory_b": b,
            "step": np.arange(length),
            "t": self._live_time(a, sol_a)[:length],
        }
        if log:
            with np.errstate(divide="ignore"):
                columns["log_distance"] = np.log(distance)
        else:
            columns["distance"] = distance

        return pd.DataFrame(columns)

    def _live_solution(self, trajectory, solutions=None):
        if solutions is None:
            return self.window.system.solution(trajectory)
        try:
            return solutions[trajectory]
        except IndexError as exc:
            raise IndexError(f"No trajectory at index {trajectory}") from exc

    def _live_time(self, trajectory, solution):
        times = self.window.system.time(trajectory)
        if len(times) == len(solution):
            return times

        t_min = self.window.system.t_min
        spec = self.window.system._trajectory_solve_spec(trajectory)
        t_max = spec.get("t_max", self.window.system.t_max)
        if len(solution) <= 0:
            return np.array([], dtype=np.float64)
        dt = (t_max - t_min) / len(solution)

        return t_min + (np.arange(len(solution), dtype=np.float64) + 1.0) * dt

    def _live_status_text(self):
        plot_count = len(self.live_plots)
        trace_count = sum(len(specs) for specs in self.live_plots.values())

        if trace_count == 0:
            return "No live plots"
        if trace_count == 1:
            return "Live: 1 trace"

        return f"Live: {trace_count} traces across {plot_count} plots"
