# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import threading
import time

import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

from ..ui.icons import icon
from .density import auto_extent, bin_points, tone_map


class _AccumulationSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, object, object, int)
    finished = QtCore.pyqtSignal(int, int)
    failed = QtCore.pyqtSignal(int, str)


class AccumulationWorker(QtCore.QRunnable):
    def __init__(self, generation, chunks, bins, extent, max_points, interval):
        super().__init__()
        self.generation = generation
        self.chunks = chunks
        self.bins = bins
        self.extent = extent
        self.max_points = max_points
        self.interval = interval / 1000
        self.signals = _AccumulationSignals()
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._resume.set()

    def run(self):
        try:
            self._accumulate()
        # not ideal but user generator code runs here and exception would get lost otherwise
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(self.generation, f"{type(exc).__name__}: {exc}")

    def _accumulate(self):
        nx, ny = self.bins
        counts = np.zeros((ny, nx))
        extent = self.extent
        total = 0
        last_sent = time.monotonic()

        for x, y in self.chunks():
            self._resume.wait()
            if self._stop.is_set():
                return

            if extent is None:
                extent = auto_extent(x, y)
            counts += bin_points(x, y, self.bins, extent)
            total += len(x)

            if self.max_points is not None and total >= self.max_points:
                break

            now = time.monotonic()
            if now - last_sent >= self.interval:
                self.signals.progress.emit(
                    self.generation, counts.copy(), extent, total
                )
                last_sent = now

        self.signals.progress.emit(self.generation, counts, extent, total)
        self.signals.finished.emit(self.generation, total)

    def pause(self):
        self._resume.clear()

    def resume(self):
        self._resume.set()

    def stop(self):
        self._stop.set()
        # resume paused worker so it can see the stop
        self._resume.set()


class Accumulation(QtCore.QObject):
    changed = QtCore.pyqtSignal()
    status_message = QtCore.pyqtSignal(str, bool)

    def __init__(
        self,
        name,
        chunks,
        item,
        *,
        bins,
        extent,
        scale,
        gamma,
        max_points,
        interval,
        parent=None,
    ):
        super().__init__(parent)
        self.name = name
        self.chunks = chunks
        self.item = item
        self.bins = bins
        self.extent = extent
        self.scale = scale
        self.gamma = gamma
        self.max_points = max_points
        self.interval = interval
        self.widget = None
        self.total = 0
        self.paused = False
        self._generation = 0
        self._worker = None

    def restart(self):
        self.stop()
        self._generation += 1
        self.total = 0

        nx, ny = self.bins
        self.item.setImage(np.zeros((ny, nx), dtype=np.float32), autoLevels=False)

        worker = AccumulationWorker(
            self._generation,
            self.chunks,
            self.bins,
            self.extent,
            self.max_points,
            self.interval,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._worker = worker
        QtCore.QThreadPool.globalInstance().start(worker)
        self.changed.emit()

    def toggle_pause(self):
        if self._worker is None:
            self.restart()
            return

        self.paused = not self.paused
        if self.paused:
            self._worker.pause()
        else:
            self._worker.resume()
        self.changed.emit()

    def stop(self):
        if self._worker is None:
            return

        self._worker.stop()
        self._worker = None
        self.paused = False
        self.changed.emit()

    def is_active(self):
        return self._worker is not None and not self.paused

    def _on_progress(self, generation, counts, extent, total):
        # progress from a stopped worker can still be queued
        if generation != self._generation:
            return

        self.item.setImage(tone_map(counts, self.scale, self.gamma), autoLevels=False)
        x0, x1, y0, y1 = extent
        self.item.setRect(x0, y0, x1 - x0, y1 - y0)
        self.total = total
        self.changed.emit()

    def _on_finished(self, generation, total):
        if generation != self._generation:
            return

        self._worker = None
        self.changed.emit()
        self.status_message.emit(f"{self.name}: finished after {total:,} points", False)

    def _on_failed(self, generation, message):
        if generation != self._generation:
            return

        self._worker = None
        self.changed.emit()
        self.status_message.emit(f"{self.name}: {message}", True)

    def __repr__(self):
        state = "running" if self.is_active() else "stopped"
        return f"Accumulation({self.name!r}, points={self.total:,}, state={state})"


class AccumulationWidget(QtWidgets.QWidget):
    def __init__(self, accumulation, parent=None):
        super().__init__(parent)
        self.accumulation = accumulation

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.points_label = QtWidgets.QLabel()

        self.play_button = QtWidgets.QToolButton()
        self.play_button.setToolTip("Pause or resume accumulation")

        self.reset_button = QtWidgets.QToolButton()
        self.reset_button.setText("Reset")
        self.reset_button.setIcon(icon("view-refresh"))
        self.reset_button.setToolTip("Clear and restart accumulation")

        layout.addWidget(QtWidgets.QLabel(accumulation.name))
        layout.addStretch(1)
        layout.addWidget(self.points_label)
        layout.addWidget(self.play_button)
        layout.addWidget(self.reset_button)

        self.play_button.clicked.connect(self.accumulation.toggle_pause)
        self.reset_button.clicked.connect(self.accumulation.restart)
        self.accumulation.changed.connect(self.sync)

        self.sync()

    def sync(self):
        active = self.accumulation.is_active()
        self.play_button.setText("Pause" if active else "Play")
        self.play_button.setIcon(
            icon("media-playback-pause" if active else "media-playback-start")
        )
        self.points_label.setText(f"{self.accumulation.total:,} points")
