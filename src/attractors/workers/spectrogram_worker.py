# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore

from ..core.signal_analysis import power_spectrogram


class _SpectrogramSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, object, str)


class SpectrogramWorker(QtCore.QRunnable):
    def __init__(
        self,
        request_id,
        signal,
        *,
        window_duration,
        overlap=0.5,
        remove_mean=True,
        window="hann",
    ):
        super().__init__()
        self.request_id = request_id
        self.signal = signal
        self.window_duration = window_duration
        self.overlap = overlap
        self.remove_mean = remove_mean
        self.window = window
        self.signals = _SpectrogramSignals()

    def run(self):
        try:
            spectrogram = power_spectrogram(
                self.signal,
                window_duration=self.window_duration,
                overlap=self.overlap,
                remove_mean=self.remove_mean,
                window=self.window,
            )
        except (ValueError, MemoryError) as exc:
            self.signals.finished.emit(
                self.request_id, None, str(exc) or type(exc).__name__
            )
        else:
            self.signals.finished.emit(self.request_id, spectrogram, "")
