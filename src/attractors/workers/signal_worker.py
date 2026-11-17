# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore


class _AnalysisSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, object, str)


class SignalWorker(QtCore.QRunnable):
    def __init__(self, request_id, signal, compute):
        super().__init__()
        self.request_id = request_id
        self.signal = signal
        self.compute = compute
        self.signals = _AnalysisSignals()

    def run(self):
        try:
            result = self.compute(self.signal)
        except (ValueError, MemoryError) as exc:
            self.signals.finished.emit(
                self.request_id, None, str(exc) or type(exc).__name__
            )
        else:
            self.signals.finished.emit(self.request_id, result, "")

