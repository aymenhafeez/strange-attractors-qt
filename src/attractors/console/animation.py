import inspect

from pyqtgraph.Qt import QtCore


class ConsoleAnimation(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(
        self, name, callback, *, interval=16, dt=None, status_callback=None, parent=None
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
        self.dt = self.interval / 1000.0 if dt is None else dt
        self.status_callback = status_callback
        self.frame = 0
        self.time = 0.0

        self.callback_accepts_animation = self.accepts_animation(callback)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.interval)
        self.timer.timeout.connect(self.step)

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
        was_active = self.timer.isActive()
        self.timer.stop()
        self.frame = 0
        self.time = 0.0
        self.step(advance=False)

        if was_active:
            self.changed.emit()

        return self

    def step(self, *, advance=True):
        try:
            if self.callback_accepts_animation:
                self.callback(self)
            else:
                self.callback()
        except Exception as e:
            self.pause()
            self.set_status(f"{self.name}: {e}")
            raise

        if advance:
            self.frame += 1
            self.time += self.dt

        self.changed.emit()

        return self

    def is_active(self):
        return self.timer.isActive()

    def set_interval(self, interval):
        self.interval = interval

        if interval < 1:
            raise ValueError("Animation interval must be at least 1ms")
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
