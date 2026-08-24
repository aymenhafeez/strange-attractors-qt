import inspect

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


class ConsoleAnimation(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(
        self,
        name,
        callback,
        *,
        interval=16,
        dt=None,
        frames=None,
        loop=True,
        status_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        key = str(name).strip()
        if not key:
            raise ValueError("Animation name can't be empty")
        if not callable(callback):
            raise TypeError("Animation callback must be callable")

        self.name = key
        self.callback = callback
        self.interval = interval
        if self.interval < 1:
            raise ValueError("Animation interval must be at least 1ms")

        self.dt = self.interval / 1000.0 if dt is None else dt
        if self.dt <= 0:
            raise ValueError("Animation dt must be positive")

        self.frames = None if frames is None else int(frames)
        if self.frames is not None and self.frames < 1:
            raise ValueError("Animation frames must be at least 1")

        self.loop = loop
        self.status_callback = status_callback
        self.frame = 0
        self.time = 0.0

        self.callback_accepts_animation = self.accepts_animation(callback)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.interval)
        self.timer.timeout.connect(self.step)

    def has_timeline(self):
        return self.frames is not None

    def _clamp_frame(self, frame):
        frame = int(frame)

        if self.frames is None:
            return max(0, frame)

        if self.loop:
            return frame % self.frames

        return max(0, min(frame, self.frames - 1))

    def seek(self, frame, *, emit=True):
        if self.frames is None:
            raise ValueError("Can't seek animation without finite frame count")

        self.frame = self._clamp_frame(frame)
        self.time = self.frame * self.dt

        return self.refresh(emit=emit)

    def _run_callback(self):
        try:
            if self.callback_accepts_animation:
                self.callback(self)
            else:
                self.callback()
        except Exception as e:
            self.pause()
            self.set_status(f"{self.name}: {e}")
            raise

    def refresh(self, *, emit=True):
        self._run_callback()

        if emit:
            self.changed.emit()

        return self

    def play(self):
        if not self.timer.isActive():
            self.timer.start()
            self.changed.emit()

        return self

    def pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.changed.emit()

        return self

    def stop(self):
        self.timer.stop()
        self.frame = 0
        self.time = 0.0
        self.refresh(emit=False)
        self.changed.emit()

        return self

    def step(self, *, emit=True):
        next_frame = self._clamp_frame(self.frame + 1)
        reached_end = (
            self.frames is not None and not self.loop and next_frame == self.frames - 1
        )

        self.frame = next_frame
        self.time = self.frame * self.dt
        self.refresh(emit=emit)

        if reached_end:
            self.timer.stop()

        return self

    def step_back(self, *, emit=True):
        if self.frame > 0:
            self.frame -= 1
            self.time = self.frame * self.dt

        return self.refresh(emit=emit)

    def is_active(self):
        return self.timer.isActive()

    def set_interval(self, interval):
        if interval < 1:
            raise ValueError("Animation interval must be at least 1ms")

        self.interval = interval
        self.timer.setInterval(interval)
        self.dt = self.interval / 1000.0
        self.changed.emit()

        return self

    def set_status(self, message):
        if self.status_callback is not None:
            self.status_callback(message)

    @staticmethod
    def accepts_animation(callback):
        signature = inspect.signature(callback)
        required = [
            param
            for param in signature.parameters.values()
            if param.default is inspect.Parameter.empty
            and param.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
        ]

        return bool(required)

    def __repr__(self):
        state = "playing" if self.is_active() else "paused"
        return f"ConsoleAnimation({self.name!r}, frame={self.frame}, state={state})"


class ConsoleAnimationWidget(QtWidgets.QWidget):
    def __init__(self, animation, parent=None):
        super().__init__(parent)
        self.animation = animation

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.name_label = QtWidgets.QLabel(animation.name)

        self.play_button = QtWidgets.QToolButton()
        self.play_button.setToolTip("Play or pause animation")

        self.stop_button = QtWidgets.QToolButton()
        self.stop_button.setText("Stop")
        self.stop_button.setIcon(QtGui.QIcon.fromTheme("media-playback-stop"))
        self.stop_button.setToolTip("Stop animation and reset to first frame")

        self.rewind_button = QtWidgets.QToolButton()
        self.rewind_button.setText("Rewind")
        self.rewind_button.setIcon(QtGui.QIcon.fromTheme("media-skip-backward"))
        self.rewind_button.setToolTip("Rewind animation to previous step")

        self.step_button = QtWidgets.QToolButton()
        self.step_button.setText("Step")
        self.step_button.setIcon(QtGui.QIcon.fromTheme("media-skip-forward"))
        self.step_button.setToolTip("Advance animation to next step")

        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 10000)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setKeyboardTracking(False)
        self.interval_spin.setValue(animation.interval)
        self.interval_spin.setToolTip("Animation interval")

        self.timeline = None
        self._resume_after_scrub = False

        if animation.has_timeline():
            self.timeline = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.timeline.setRange(0, animation.frames - 1)
            self.timeline.setValue(animation.frame)
            self.timeline.setToolTip("Animation timeline")

        layout.addWidget(self.name_label)

        if self.timeline is not None:
            layout.addWidget(self.timeline)
        else:
            layout.addStretch(1)

        # layout.addStretch(1)
        layout.addWidget(self.rewind_button)
        layout.addWidget(self.play_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.step_button)

        layout.addWidget(self.interval_spin)

        self.play_button.clicked.connect(self.toggle_play)
        self.stop_button.clicked.connect(self.animation.stop)
        self.step_button.clicked.connect(self.animation.step)
        self.rewind_button.clicked.connect(self.animation.step_back)
        self.interval_spin.valueChanged.connect(self.animation.set_interval)
        self.animation.changed.connect(self.sync)

        if self.timeline is not None:
            self.timeline.sliderPressed.connect(self.begin_scrub)
            self.timeline.sliderMoved.connect(self.animation.seek)
            self.timeline.sliderReleased.connect(self.end_scrub)

        self.sync()

    def begin_scrub(self):
        self._resume_after_scrub = self.animation.is_active()
        self.animation.pause()

    def end_scrub(self):
        if self.timeline is not None:
            self.animation.seek(self.timeline.value())

        if self._resume_after_scrub:
            self.animation.play()

        self._resume_after_scrub = False

    def toggle_play(self):
        if self.animation.is_active():
            self.animation.pause()
        else:
            self.animation.play()

    def sync(self):
        pause_icon = QtGui.QIcon.fromTheme("media-playback-pause")
        play_icon = QtGui.QIcon.fromTheme("media-playback-start")
        self.play_button.setText("Pause" if self.animation.is_active() else "Play")
        self.play_button.setIcon(
            pause_icon if self.animation.is_active() else play_icon
        )

        if self.timeline is not None and not self.timeline.isSliderDown():
            with QtCore.QSignalBlocker(self.timeline):
                self.timeline.setValue(self.animation.frame)

        with QtCore.QSignalBlocker(self.interval_spin):
            self.interval_spin.setValue(self.animation.interval)
