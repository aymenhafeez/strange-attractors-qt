from pyqtgraph.Qt import QtCore

ANIMATION_INTERVAL_MS = 16


class AnimationController:
    def __init__(self, on_frame, on_visibility_changed, timer=None, parent=None):
        self._on_frame = on_frame
        self._on_visibility_changed = on_visibility_changed
        self._timer = timer or QtCore.QTimer(parent)
        if timer is None:
            self._timer.timeout.connect(self._tick)
        self._frame = 0
        self._step = 100

    @property
    def frame(self):
        return self._frame

    def reset_frame(self):
        self._frame = 0

    def set_step(self, step):
        self._step = max(1, int(step))

    def toggle(self):
        if self._timer.isActive():
            self.stop()
            return False

        self._frame = 0
        self._timer.start(ANIMATION_INTERVAL_MS)
        self._on_visibility_changed()
        return True

    def stop(self):
        self._timer.stop()
        self._on_visibility_changed()

    def is_active(self):
        return self._timer.isActive()

    def _tick(self):
        self.advance()

    def advance(self):
        finished = self._on_frame(self._frame, self._step)
        if finished is None:
            return None

        self._frame = finished["frame"]
        if finished["done"]:
            self.stop()
        return finished
