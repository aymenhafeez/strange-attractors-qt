import numpy as np
from pyqtgraph.Qt import QtCore, QtGui

ORBIT_INTERVAL = 30  # ms
ORBIT_STEP_DEGREES = 0.25


class CameraController:
    def __init__(self, view, parent=None, orbit_timer=None):
        self.view = view
        self._orbit_speed = 100
        self._orbit_timer = orbit_timer or QtCore.QTimer(parent)
        if orbit_timer is None:
            self._orbit_timer.timeout.connect(self._orbit_frame)

    def set_camera(self, config):
        self.view.setCameraPosition(
            pos=QtGui.QVector3D(0, 0, config.pan),
            distance=config.camera_distance,
            elevation=config.camera_elevation,
            azimuth=config.camera_azimuth,
        )

    def get_camera_state(self):
        center = self.view.opts.get("center", QtGui.QVector3D(0, 0, 0))
        return {
            "distance": float(self.view.opts.get("distance", 0.0)),
            "elevation": float(self.view.opts.get("elevation", 0.0)),
            "azimuth": float(self.view.opts.get("azimuth", 0.0)),
            "center": [float(center.x()), float(center.y()), float(center.z())],
        }

    def fit_camera_to_solutions(self, solutions):
        if not solutions:
            return

        points = np.concatenate(solutions, axis=0)
        if points.size == 0:
            return

        finite = np.all(np.isfinite(points), axis=1)
        if not np.any(finite):
            return

        points = points[finite]
        mins = np.min(points, axis=0)
        maxs = np.max(points, axis=0)
        center = 0.5 * (mins + maxs)
        span = np.max(maxs - mins)
        distance = max(float(span) * 1.25, 1.0)

        self.view.setCameraPosition(
            pos=QtGui.QVector3D(float(center[0]), float(center[1]), float(center[2])),
            distance=distance,
        )

    def set_orbit_mode(self, enabled):
        if enabled:
            if not self._orbit_timer.isActive():
                self._orbit_timer.start(ORBIT_INTERVAL)
        else:
            self._orbit_timer.stop()

    def set_orbit_speed(self, speed):
        self._orbit_speed = max(1, int(speed))

    def _orbit_frame(self):
        step = ORBIT_STEP_DEGREES * (self._orbit_speed / 100.0)
        self.view.orbit(step, 0)
