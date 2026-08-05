import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtGui

DEFAULT_GRID_HALF_SIZE = 50.0
GRID_PADDING_FACTOR = 4.0
MAX_GRID_HALF_SIZE = 750.0


class GridOverlay:
    def __init__(self, view):
        self.view = view
        self._grid_visible = True
        self.grid_half_size = DEFAULT_GRID_HALF_SIZE
        self.grid_items = []
        self._poincare_axis = None
        self._poincare_value = 0.0
        self._poincare_plane_items = []

    def build_grid(self, half_size):
        for item in self.grid_items:
            self.view.removeItem(item)
        self.grid_items.clear()

        is_visible = self._grid_visible

        self.grid_half_size = half_size
        ideal_spacing = half_size / 4
        spacing = max(
            1.0, round(ideal_spacing, -int(np.floor(np.log10(ideal_spacing))))
        )
        num_divisions = max(4, round(half_size * 2 / spacing))
        spacing = half_size * 2 / num_divisions

        grid_faces = [
            ("XY", [], (0, 0, -half_size)),
            ("YZ", [(90, 1, 0, 0)], (0, -half_size, 0)),
            ("XZ", [(90, 0, 1, 0)], (-half_size, 0, 0)),
            ("YX", [], (0, 0, half_size)),
            ("ZY", [(90, 1, 0, 0)], (0, half_size, 0)),
            ("ZX", [(90, 0, 1, 0)], (half_size, 0, 0)),
        ]
        tick_positions = np.linspace(-half_size, half_size, num_divisions + 1)
        tick_values = [round(v, 0) for v in tick_positions]

        for i, (_, rotations, (dx, dy, dz)) in enumerate(grid_faces):
            g = gl.GLGridItem()
            g.setSize(x=half_size * 2, y=half_size * 2, z=1)
            g.setSpacing(x=spacing, y=spacing, z=1)
            for angle, *axis in rotations:
                g.rotate(angle, *axis)
            g.translate(dx, dy, dz)
            self.view.addItem(g)
            self.grid_items.append(g)
            g.setVisible(is_visible)

            if i < 3:
                for val in tick_values:
                    if abs(val) < 1e-5:
                        continue
                    offset = spacing * 0.3
                    t1 = gl.GLTextItem(
                        pos=[val, -offset, 0],
                        text=str(val),
                        color=(255, 255, 255, 100),
                        font=QtGui.QFont("Sans", 10),
                    )
                    t2 = gl.GLTextItem(
                        pos=[-offset, val, 0],
                        text=str(val),
                        color=(255, 255, 255, 100),
                        font=QtGui.QFont("Sans", 10),
                    )
                    for angle, *axis in rotations:
                        t1.rotate(angle, *axis)
                        t2.rotate(angle, *axis)
                    t1.translate(dx, dy, dz)
                    t2.translate(dx, dy, dz)
                    t1.setVisible(is_visible)
                    t2.setVisible(is_visible)
                    self.view.addItem(t1)
                    self.view.addItem(t2)
                    self.grid_items.append(t1)
                    self.grid_items.append(t2)

        if self._poincare_axis is not None:
            self._update_poincare_plane()

    def set_grid_visible(self, visible):
        self._grid_visible = visible
        for item in self.grid_items:
            item.setVisible(visible)

    def set_poincare_plane(self, axis, value):
        self._poincare_axis = axis
        self._poincare_value = value
        self._update_poincare_plane()

    def remove_poincare_plane(self):
        self._poincare_axis = None
        for item in self._poincare_plane_items:
            self.view.removeItem(item)
        self._poincare_plane_items.clear()

    def _update_poincare_plane(self):
        for item in self._poincare_plane_items:
            self.view.removeItem(item)
        self._poincare_plane_items.clear()

        if self._poincare_axis is None:
            return

        half = self.grid_half_size
        axis = self._poincare_axis
        value = self._poincare_value

        if axis == "x":
            verts = np.array(
                [
                    [value, -half, -half],
                    [value, half, -half],
                    [value, half, half],
                    [value, -half, half],
                ],
                dtype=np.float64,
            )
        elif axis == "y":
            verts = np.array(
                [
                    [-half, value, -half],
                    [half, value, -half],
                    [half, value, half],
                    [-half, value, half],
                ],
                dtype=np.float64,
            )
        else:
            verts = np.array(
                [
                    [-half, -half, value],
                    [half, -half, value],
                    [half, half, value],
                    [-half, half, value],
                ],
                dtype=np.float64,
            )

        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
        vc = np.full((4, 4), [1.0, 0.3, 0.3, 0.35], dtype=np.float32)

        mesh = gl.GLMeshItem(
            vertexes=verts,
            faces=faces,
            vertexColors=vc,
            smooth=False,
            glOptions="translucent",
        )
        self.view.addItem(mesh)
        self._poincare_plane_items.append(mesh)

        border_verts = np.array(
            [
                verts[0],
                verts[1],
                verts[2],
                verts[3],
                verts[0],
            ],
            dtype=np.float64,
        )
        border = gl.GLLinePlotItem(
            pos=border_verts,
            color=(1.0, 0.3, 0.3, 0.7),
            width=1.5,
            glOptions="translucent",
        )
        self.view.addItem(border)
        self._poincare_plane_items.append(border)

    def auto_adjust_grid(self, solutions):
        if not solutions:
            return

        points = np.concatenate(solutions, axis=0)
        if points.size == 0:
            return

        finite_points = points[np.isfinite(points).all(axis=1)]
        if len(finite_points) == 0:
            return

        new_half = min(
            max(
                float(np.max(np.abs(finite_points))) * GRID_PADDING_FACTOR,
                DEFAULT_GRID_HALF_SIZE,
            ),
            MAX_GRID_HALF_SIZE,
        )
        if abs(new_half - self.grid_half_size) / max(self.grid_half_size, 1e-6) > 0.1:
            self.build_grid(new_half)
