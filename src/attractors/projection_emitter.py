import numpy as np


class ProjectionEmitter:
    def __init__(self, signal):
        self._signal = signal

    def emit_segments(self, segments):
        if not segments:
            return False

        all_points = np.concatenate(segments, axis=0)
        finite = np.all(np.isfinite(all_points), axis=1)
        if not np.any(finite):
            return False

        x, y, z = all_points[finite].T
        self._signal.emit(x, y, z)
        return True
