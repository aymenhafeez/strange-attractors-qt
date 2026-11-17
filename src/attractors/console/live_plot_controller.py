# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import itertools
from dataclasses import dataclass

import pandas as pd
from pyqtgraph.Qt import QtCore

from ..ui.style import plot_colours
from .explorer import PLOT_MODE_OVERLAY, PLOT_MODE_REPLACE, parse_mode
from .system import SEPARATION_WINDOW

PREVIEW_UPDATE_INTERVAL = 120  # ms
TIMESERIES = {"displacement", "radius", "speed"}

SERIES = {
    "axis": lambda system, spec, solutions: system.axis_series(
        spec["axis"], spec["trajectory"], solutions
    ),
    **{
        kind: lambda system, spec, solutions, kind=kind: system.derived_series(
            kind, spec["trajectory"], solutions
        )
        for kind in TIMESERIES
    },
    "projection": lambda system, spec, solutions: system.projection_series(
        spec["x_axis"], spec["y_axis"], spec["trajectory"], solutions
    ),
    "separation": lambda system, spec, _solutions: system.separation_series(
        spec["a"], spec["b"], spec["log"]
    ),
    "separation_fit": lambda system, spec, _solutions: system.separation_fit_series(
        spec["a"], spec["b"], **{key: spec[key] for key in SEPARATION_WINDOW}
    ),
    "vector_field": lambda system, spec, _solutions: system.vector_field_series(
        spec["x_axis"],
        spec["y_axis"],
        fixed_axis=spec["fixed_axis"],
        fixed_value=spec["fixed_value"],
        x_range=spec["x_range"],
        y_range=spec["y_range"],
        density=spec["density"],
        scale=spec["scale"],
        colour_by_speed=spec["colour_by_speed"],
        speed_bands=spec["speed_bands"],
    ),
}
PREVIEW = set(SERIES)
TIMESERIES = {"displacement", "radius", "speed"}


# tracks by plot object not name so rename keeps the trace
@dataclass(eq=False)
class _Trace:
    plot: object
    spec: dict
    items: tuple = ()


class LivePlotController(QtCore.QObject):
    changed = QtCore.pyqtSignal()
    trace_failed = QtCore.pyqtSignal(str)

    def __init__(self, system, plots, system_toolbar, parent=None):
        super().__init__(parent)
        self._system = system
        self._plots = plots
        self._toolbar = system_toolbar
        self._traces = {}
        self._ids = itertools.count(1)
        self._auto_pen_indices = {}
        self._last_preview_update = None
        # plots.plots_changed.connect(self._on_plots_changed)
        plots.views_changed.connect(self._on_plots_changed)

    def trace(self, trace_id):
        try:
            return self._traces[trace_id]
        except KeyError:
            raise LookupError(f"Live trace {trace_id} was removed") from None

    def _named(self, plot_name):
        return [
            (trace_id, trace)
            for trace_id, trace in self._traces.items()
            if trace.spec["plot"] == plot_name
        ]

    def _on(self, plot):
        return [trace for trace in self._traces.values() if trace.plot is plot]

    def _drop(self, plot):
        for trace_id, trace in list(self._traces.items()):
            if trace.plot is plot:
                del self._traces[trace_id]

    def _forget(self, plot):
        self._drop(plot)
        self._auto_pen_indices.pop(plot, None)

    def rename_plot(self, old_name, new_name):
        self._plots.rename(old_name, new_name)

    def tooltip(self, plot_name):
        count = len(self._named(plot_name))
        traces = "trace" if count == 1 else "traces"

        return f"{plot_name}: {count or 'no'} live {traces}"

    def sync_menu(self, plot_name):
        traces = [
            {
                "id": trace_id,
                "label": (
                    f"{self._live_trace_label(trace.spec)} "
                    f"(unavailable: {trace.spec['error']})"
                    if trace.spec.get("error")
                    else self._live_trace_label(trace.spec)
                ),
                "mode": self._live_trace_mode(trace.spec),
            }
            for trace_id, trace in self._named(plot_name)
        ]
        self._toolbar.set_live_traces(plot_name, traces)

    def _live_trace_label(self, spec):
        if spec["label"]:
            return str(spec["label"])

        kind = spec["kind"]
        if kind == "axis":
            return f"T{spec['trajectory']} {spec['axis']}"
        if kind in TIMESERIES:
            return f"T{spec['trajectory']} {kind}"
        if kind == "projection":
            return f"T{spec['trajectory']} {spec['x_axis']}-{spec['y_axis']}"
        if kind == "separation":
            prefix = "log sep" if spec["log"] else "sep"
            return f"T{spec['a']}-T{spec['b']} {prefix}"
        if kind == "separation_fit":
            return f"T{spec['a']}-T{spec['b']} sep fit"
        if kind == "vector_field":
            fixed = spec["fixed_axis"]
            section = "" if fixed is None else f" {fixed}={spec['fixed_value']:g}"
            return f"{spec['x_axis']}-{spec['y_axis']} field{section}"

        return kind

    def _live_trace_mode(self, spec):
        if spec["kind"] in PREVIEW:
            return "live preview"

        return "full solve"

    def on_plot_requested(self, kind, options):
        plot_options = dict(options)
        live = bool(plot_options.pop("live", True))
        plot = plot_options.pop("plot", None)
        if live and kind in PREVIEW:
            self.register(kind, plot=plot, **plot_options)
        else:
            self._run_console_plot_request(kind, plot=plot, **plot_options)

    def _auto_pen(self, plot, mode):
        if mode == PLOT_MODE_OVERLAY:
            index = self._auto_pen_indices.get(plot, 0)
        else:
            index = 0

        pens = plot_colours()["plot_auto_pens"]
        pen = pens[index % len(pens)]
        self._auto_pen_indices[plot] = index + 1

        return pen

    def _plot_pen(self, plot, mode, pen):
        if pen is None:
            return self._auto_pen(plot, mode)

        if mode != PLOT_MODE_OVERLAY:
            self._auto_pen_indices[plot] = 0

        return pen

    def _run_console_plot_request(
        self,
        kind,
        *,
        plot=None,
        mode=PLOT_MODE_REPLACE,
        label=None,
        pen=None,
        **options,
    ):
        target = self._live_plot_target(self._plot_name(plot))
        mode = parse_mode(mode)
        pen = self._plot_pen(target, mode, pen)
        if mode == PLOT_MODE_REPLACE:
            self._drop(target)

        if kind == "crossings":
            self._system.plot_crossings(
                options["axis"],
                options["value"],
                direction=options["direction"],
                trajectory=options["trajectory"],
                plot=target,
                mode=mode,
                pen=pen,
            )
        else:
            self._system.draw_series(
                self._series({"kind": kind, **options}),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
            )
        self.changed.emit()

    def _on_plots_changed(self):
        names = {
            self._plots.get(name, activate=False): name for name in self._plots.names()
        }
        for trace_id, trace in list(self._traces.items()):
            if trace.plot in names:
                trace.spec["plot"] = names[trace.plot]
            else:
                del self._traces[trace_id]
        for plot in list(self._auto_pen_indices):
            if plot not in names:
                del self._auto_pen_indices[plot]

        self.changed.emit()

    def clear_plot(self):
        plot = self._plots.current
        self._plots.clear()
        self._forget(plot)
        self.changed.emit()

    def clear_all(self):
        self._plots.clear_all()
        self._traces.clear()
        self._auto_pen_indices.clear()
        self.changed.emit()

    def register(self, kind, *, plot=None, mode=PLOT_MODE_REPLACE, **options):
        plot_name = self._plot_name(plot)
        target = self._live_plot_target(plot_name)
        mode = parse_mode(mode)
        pen = self._plot_pen(target, mode, options.pop("pen", None))
        spec = {
            "source": "main",
            "kind": kind,
            "plot": plot_name,
            "mode": mode,
            "pen": pen,
            **options,
        }
        if mode == PLOT_MODE_REPLACE:
            self._drop(target)
        trace_id = next(self._ids)
        self._traces[trace_id] = _Trace(target, spec)
        self._refresh_plot(target)
        self.changed.emit()

        return trace_id

    def frame(self):
        rows = [
            {**trace.spec, "trace": trace_id}
            for trace_id, trace in self._traces.items()
        ]
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

    def unfollow(self, plot=None):
        if plot is None:
            plot_name = self._plots.current_name
        else:
            plot_name = str(plot).strip()

        if not plot_name:
            raise ValueError("Plot name cannot be empty")

        target = self._live_plot_target(plot_name)
        self._forget(target)
        target.clear()
        self.changed.emit()

        return self.frame()

    def remove(self, trace_id):
        plot = self.trace(trace_id).plot
        del self._traces[trace_id]
        plot.clear()

        remaining = self._on(plot)
        for trace in remaining:
            trace.items = ()

        if remaining:
            self._refresh_plot(plot)
        self.changed.emit()

        return self.frame()

    def unfollow_all(self):
        self._traces.clear()
        self._auto_pen_indices.clear()
        self.changed.emit()

        return self.frame()

    def _plot_name(self, plot):
        if plot is None:
            return self._plots.current_name

        plot_name = str(plot).strip()
        self._plots.new(plot_name)

        return plot_name

    def _live_plot_target(self, plot_name):
        return self._plots.new(plot_name, activate=False)

    def _set_trace_error(self, trace, error=None):
        previous = trace.spec.get("error")

        if error is None:
            trace.spec.pop("error", None)
        else:
            trace.spec["error"] = error

        for item in trace.items:
            item.setVisible(error is None)

        if previous != error:
            self.changed.emit()
            if error is not None:
                label = self._live_trace_label(trace.spec)
                self.trace_failed.emit(f"{trace.spec['plot']}: {label}: {error}")

    def _refresh_plot(self, plot):
        for position, trace in enumerate(self._on(plot)):
            try:
                self._plot_trace(trace, replace=position == 0)
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                self._set_trace_error(trace, str(exc))
            else:
                self._set_trace_error(trace)

    def refresh_all(self):
        self._last_preview_update = None
        for plot in dict.fromkeys(trace.plot for trace in self._traces.values()):
            self._refresh_plot(plot)

    def refresh_preview(self, solutions=None, *, kinds=None):
        if not any(trace.items for trace in self._traces.values()):
            return

        preview_kinds = PREVIEW if kinds is None else set(kinds)
        now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        last_update = self._last_preview_update
        if (
            solutions is None
            and last_update is not None
            and now_ms - last_update < PREVIEW_UPDATE_INTERVAL
        ):
            return

        refreshed = False
        for trace in list(self._traces.values()):
            if trace.spec["kind"] not in preview_kinds:
                continue
            try:
                updated = self._update_items(trace, solutions=solutions)
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                self._set_trace_error(trace, str(exc))
            else:
                if updated:
                    self._set_trace_error(trace)
                    refreshed = True

        if refreshed:
            self._last_preview_update = now_ms

    def _series(self, spec, solutions=None):
        return SERIES[spec["kind"]](self._system, spec, solutions)

    def _plot_trace(self, trace, *, replace):
        if self._update_items(trace):
            return

        spec = trace.spec
        trace.items = tuple(
            self._system.draw_series(
                self._series(spec),
                plot=trace.plot,
                mode=PLOT_MODE_REPLACE if replace else PLOT_MODE_OVERLAY,
                pen=spec["pen"],
                fit_pen=spec.get("fit_pen"),
                label=spec["label"] or self._live_trace_label(spec),
                zoom_region=spec.get("zoom_region", False),
            )
        )

    def _update_items(self, trace, *, solutions=None):
        items = trace.items
        target = trace.plot
        if not items or not all(target.has_item(item) for item in items):
            return False

        series = self._series(trace.spec, solutions)
        if len(series) != len(items):
            return False

        for item, line in zip(items, series, strict=True):
            item.setData(line.x, line.y)
        target.set_labels(bottom=series[-1].bottom, left=series[-1].left)

        return True
