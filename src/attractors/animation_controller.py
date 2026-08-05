from pyqtgraph.Qt import QtCore

ANIMATION_INTERVAL = 16  # ms


class AnimationController:
    def __init__(
        self,
        on_frame,
        on_visibility_changed,
        on_finished=None,
        parent=None,
    ):
        self._on_frame = on_frame
        self._on_visibility_changed = on_visibility_changed
        self._on_finished = on_finished
        self._timer = QtCore.QTimer(parent)
        self._timer.timeout.connect(self.advance)
        self._frame = 0
        self._step = 100
        self._loop = False

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
        self._timer.start(ANIMATION_INTERVAL)
        self._on_visibility_changed()
        return True

    def stop(self):
        self._timer.stop()
        self._on_visibility_changed()

    def is_active(self):
        return self._timer.isActive()

    def set_loop(self, checked):
        self._loop = checked

    def advance(self):
        finished = self._on_frame(self._frame, self._step)
        if finished is None:
            return None

        self._frame = finished["frame"]
        if finished["done"]:
            if self._loop:
                self._frame = 0
            else:
                self.stop()
                if self._on_finished is not None:
                    self._on_finished()
        return finished
