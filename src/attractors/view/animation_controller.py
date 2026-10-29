# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

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
        self._finished = False

    @property
    def frame(self):
        return self._frame

    def reset_frame(self, frame=0, *, finished=False):
        self._frame = frame
        self._finished = finished

    def set_step(self, step):
        self._step = max(1, int(step))

    def toggle(self):
        if self._timer.isActive():
            self.stop()
            return False

        if self._finished:
            self.reset_frame()

        self._timer.start(ANIMATION_INTERVAL)
        self._on_visibility_changed()
        return True

    def stop(self):
        self._timer.stop()
        self._on_visibility_changed()

    def seek(self, frame):
        self.stop()
        result = self._on_frame(frame, 0)
        if result is None:
            return

        self._frame = result["frame"]
        self._finished = result["done"]
        self._on_visibility_changed()

    def is_active(self):
        return self._timer.isActive()

    def set_loop(self, checked):
        self._loop = checked

    def advance(self):
        if self._finished and self._loop:
            self.reset_frame()

        result = self._on_frame(self._frame, self._step)
        if result is None:
            self.stop()
            return None

        self._frame = result["frame"]
        self._finished = result["done"]

        if self._finished and not self._loop:
            self.stop()
            if self._on_finished is not None:
                self._on_finished()

        return result
