# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pyqtgraph.Qt import QtCore

from ..ui.style import plot_colours
from .system import PLOT_MODE_OVERLAY, PLOT_MODE_REPLACE, parse_mode

PREVIEW_UPDATE_INTERVAL = 120  # ms
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


# tracks by plot object not name so rename keeps the trace
@dataclass(eq=False)
class _Trace:
    plot: object
    spec: dict
    items: tuple = ()


class LivePlotController(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self, system, plots, system_toolbar, parent=None):
        super().__init__(parent)
        self._system = system
        self._plots = plots
        self._toolbar = system_toolbar
        self._traces = {}
        self._ids = itertools.count(1)
        self._auto_pen_indices = {}
        self._last_preview_update = None
        plots.plots_changed.connect(self._on_plots_changed)

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
        try:
            self._plots.rename(old_name, new_name)
        except (KeyError, ValueError) as exc:
            self._toolbar.set_status(str(exc))

    def tooltip(self, plot_name):
        count = len(self._named(plot_name))
        if count == 0:
            return f"{plot_name}: no live traces"
        if count == 1:
            return f"{plot_name}: 1 live trace"

        return f"{plot_name}: {count} live traces"

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

    def _run_console_plot_request(self, kind, *, plot=None, **options):
        target = self._live_plot_target(self._plot_name(plot))
        mode = parse_mode(options.pop("mode", PLOT_MODE_REPLACE))
        label = options.pop("label", None)
        pen = self._plot_pen(target, mode, options.pop("pen", None))

        if mode == PLOT_MODE_REPLACE:
            self._drop(target)

        plotter, args, kwargs, accepts_label = self._console_plot_call(kind, options)
        if accepts_label:
            kwargs["label"] = label
        if pen is not None:
            kwargs["pen"] = pen
        plotter(*args, plot=target, mode=mode, **kwargs)

        self._toolbar.set_status(f"Ran {kind} plot")
        self.changed.emit()

    def _console_plot_call(self, kind, options):
        if kind == "axis":
            return (
                self._system.plot_axis,
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
                self._system.plot_projection,
                (options.get("x_axis", "x"), options.get("y_axis", "y")),
                {"trajectory": options.get("trajectory", 0)},
                True,
            )
        if kind == "separation":
            return (
                self._system.plot_separation,
                (options.get("a", 0), options.get("b", 1)),
                {"log": options.get("log", False)},
                True,
            )
        if kind == "separation_fit":
            return (
                self._system.plot_separation_fit,
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
                self._system.plot_crossings,
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
        self._toolbar.set_status(self._live_status_text())
        self.changed.emit()

    def clear_all(self):
        self._plots.clear_all()
        self._traces.clear()
        self._auto_pen_indices.clear()
        self._toolbar.set_status("Cleared live plots")
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
        self._toolbar.set_status(self._live_status_text())
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
        else:
            self._toolbar.set_status(self._live_status_text())
        self.changed.emit()

        return self.frame()

    def unfollow_all(self):
        self._traces.clear()
        self._auto_pen_indices.clear()
        self._toolbar.set_status("No live plots")
        self.changed.emit()

        return self.frame()

    def _plot_name(self, plot):
        if plot is None:
            return self._plots.current_name

        plot_name = str(plot).strip()
        if not plot_name:
            raise ValueError("Plot name cannot be empty")
        if plot_name not in self._plots.names():
            self._plots.new(plot_name)
        else:
            self._plots.get(plot_name)

        return plot_name

    def _live_plot_target(self, plot_name):
        try:
            return self._plots.get(plot_name, activate=False)
        except KeyError:
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

    def _refresh_plot(self, plot):
        errors = []

        for position, trace in enumerate(self._on(plot)):
            try:
                self._plot_trace(trace, replace=position == 0)
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                message = str(exc)
                self._set_trace_error(trace, message)
                errors.append(message)
            else:
                self._set_trace_error(trace)

        self._toolbar.set_status(
            "; ".join(errors) if errors else self._live_status_text()
        )

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
            if trace.spec.get("kind") not in preview_kinds:
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

    def _plot_trace(self, trace, *, replace):
        if self._update_items(trace):
            return

        spec = trace.spec
        kind = spec["kind"]
        target = trace.plot
        mode = PLOT_MODE_REPLACE if replace else PLOT_MODE_OVERLAY
        pen = spec.get("pen")
        label = spec.get("label") or self._live_trace_label(spec)
        if kind == "axis":
            item = self._system.plot_axis(
                spec["axis"],
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
        elif kind in TIMESERIES:
            item = self._plot_derived_timeseries(
                kind,
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
        elif kind == "projection":
            item = self._system.plot_projection(
                spec.get("x_axis", "x"),
                spec.get("y_axis", "y"),
                trajectory=spec.get("trajectory", 0),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
            )
        elif kind == "separation":
            item = self._system.plot_separation(
                spec.get("a", 0),
                spec.get("b", 1),
                log=spec.get("log", False),
                plot=target,
                mode=mode,
                pen=pen,
                label=label,
                zoom_region=spec.get("zoom_region", False),
            )
        elif kind == "separation_fit":
            item = self._plot_live_separation_fit(
                spec,
                target,
                mode=mode,
                pen=pen,
                label=label,
            )
        elif kind == "vector_field":
            item = self._system.plot_vector_field(
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
        else:
            raise ValueError(f"Unknown live plot kind: {kind}")

        trace.items = item if isinstance(item, tuple) else (item,)

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
            return self._system.plot_displacement(**kwargs)
        if kind == "radius":
            return self._system.plot_radius(**kwargs)
        if kind == "speed":
            return self._system.plot_speed(**kwargs)

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

    def _update_items(self, trace, *, solutions=None):
        items = trace.items
        target = trace.plot
        if not items or not all(target.has_item(item) for item in items):
            return False

        spec = trace.spec
        if spec.get("kind") == "separation_fit":
            separation_item, fit_item = items
            data = self._live_separation_fit_data(spec, solutions=solutions)
            separation_item.setData(data["separation_t"], data["log_distance"])
            fit_item.setData(data["fit_t"], data["fit_y"])
            target.set_labels(bottom="t", left=data["axis_label"])
        elif spec.get("kind") == "vector_field":
            data = self._live_vector_field_data(spec)
            segments = data.get("segments")
            if segments is None:
                items[0].setData(data["x"], data["y"])
            elif len(items) != len(segments):
                return False
            else:
                for item, (x_data, y_data, _pen) in zip(items, segments):
                    item.setData(x_data, y_data)
            target.set_labels(bottom=data["bottom"], left=data["left"])
        else:
            x_data, y_data, bottom, left = self._live_trace_data(
                spec,
                solutions=solutions,
            )
            items[0].setData(x_data, y_data)
            target.set_labels(bottom=bottom, left=left)

        return True

    def _live_trace_data(self, spec, *, solutions=None):
        kind = spec["kind"]
        if kind == "axis":
            axis = str(spec["axis"]).lower()
            column = self._system._axis_column(axis)
            trajectory = spec.get("trajectory", 0)
            solution = self._live_solution(trajectory, solutions)
            return (
                self._live_time(trajectory, solution),
                solution[:, column],
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
            x_column = self._system._axis_column(x_axis)
            y_column = self._system._axis_column(y_axis)
            trajectory = spec.get("trajectory", 0)
            solution = self._live_solution(trajectory, solutions)
            return (
                solution[:, x_column],
                solution[:, y_column],
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

            frame = self._system.separation(a, b, log=log)
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
        frame = self._system.vector_field_slice(
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
                "segments": self._system._vector_field_speed_bands(
                    frame,
                    x_axis,
                    y_axis,
                    spec.get("scale", 0.75),
                    spec.get("speed_bands", 5),
                ),
                "bottom": x_axis,
                "left": y_axis,
            }

        x_data, y_data = self._system._vector_field_segments(
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

        fit = self._system._fit_log_separation(fit_frame)
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
            return self._system.separation(a, b, log=log)

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
            return self._system.solution(trajectory)
        try:
            return solutions[trajectory]
        except IndexError as exc:
            raise IndexError(f"No trajectory at index {trajectory}") from exc

    def _live_time(self, trajectory, solution):
        times = self._system.time(trajectory)
        if len(times) == len(solution):
            return times

        t_min = self._system.t_min
        spec = self._system._trajectory_solve_spec(trajectory)
        t_max = spec["t_max"]
        if len(solution) <= 0:
            return np.array([], dtype=np.float64)
        dt = (t_max - t_min) / len(solution)

        return t_min + (np.arange(len(solution), dtype=np.float64) + 1.0) * dt

    def _live_status_text(self):
        plot_count = len({trace.plot for trace in self._traces.values()})
        trace_count = len(self._traces)

        if trace_count == 0:
            return "No live plots"
        if trace_count == 1:
            return "Live: 1 trace"

        return f"Live: {trace_count} traces across {plot_count} plots"
