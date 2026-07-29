import psutil
from pyqtgraph.Qt import QtCore, QtWidgets

PROCESS_STATUS_INTERVAL_MS = 1000
BYTES_PER_MIB = 1024 * 1024
BYTES_PER_GIB = 1024 * BYTES_PER_MIB


def format_memory_usage(size_bytes):
    size_bytes = int(size_bytes)
    if size_bytes >= BYTES_PER_GIB:
        return f"{size_bytes / BYTES_PER_GIB:.1f} GB"

    return f"{round(size_bytes / BYTES_PER_MIB)} MB"


def format_process_usage(cpu_percent, rss_bytes):
    return f"CPU {cpu_percent:.0f}%   RAM {format_memory_usage(rss_bytes)}"


class ProcessUsageSampler:
    def __init__(self, process=None):
        self._process = process or psutil.Process()
        self._process.cpu_percent(interval=None)

    def sample(self):
        with self._process.oneshot():
            cpu_percent = self._process.cpu_percent(interval=None)
            rss_bytes = self._process.memory_info().rss

        return cpu_percent, rss_bytes


class ProcessUsageStatus(QtWidgets.QLabel):
    def __init__(self, sampler=None, parent=None):
        super().__init__("CPU 0%   RAM 0 MB", parent)
        self._sampler = sampler or ProcessUsageSampler()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(PROCESS_STATUS_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)

        self.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.setMinimumWidth(132)
        self.setStyleSheet("border: none; padding: 0 4px; font-size: 13px;")
        self.setToolTip("Process CPU and RAM usage")

    def set_active(self, active):
        if active:
            self.refresh()
            self._timer.start()
            return

        self._timer.stop()

    def refresh(self):
        try:
            cpu_percent, rss_bytes = self._sampler.sample()
        except psutil.Error:
            self.setText("CPU unavailable   RAM unavailable")
            return

        self.setText(format_process_usage(cpu_percent, rss_bytes))
