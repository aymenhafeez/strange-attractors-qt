# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore

from ..core.signal_analysis import power_spectral_density


class _SpectrumSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, object, str)


class SpectrumWorker(QtCore.QRunnable):
    def __init__(self, request_id, signal, *, remove_mean=True, window="hann"):
        super().__init__()
        self.request_id = request_id
        self.signal = signal
        self.remove_mean = remove_mean
        self.window = window
        self.signals = _SpectrumSignals()

    def run(self):
        try:
            spectrum = power_spectral_density(
                self.signal,
                remove_mean=self.remove_mean,
                window=self.window,
            )
        except Exception as exc:  # noqa: BLE001
            self.signals.finished.emit(self.request_id, None, str(exc))
        else:
            self.signals.finished.emit(self.request_id, spectrum, "")
