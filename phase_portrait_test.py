# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np
from pyqtgraph.Qt import QtWidgets

from attractors.core.expression_parser import compile_system
from attractors.core.solver import solve_rk4
from attractors.ui.phase_panel import PhasePortraitPanel


def main():
    app = QtWidgets.QApplication([])

    panel = PhasePortraitPanel()
    panel.setWindowTitle("2D phase portrait preview")
    panel.resize(800, 600)

    equation, _ = compile_system(("y", "-x"))
    params = np.array([], dtype=np.float64)

    solutions = [
        solve_rk4(
            equation,
            np.array([radius, 0.0], dtype=np.float64),
            0.0,
            2.0 * np.pi,
            1000,
            params,
        )
        for radius in (0.5, 1.0, 1.5)
    ]

    panel.display_solutions(solutions)
    panel.seed_requested.connect(
        lambda x, y: print(f"Requested initial condition: ({x:.4f}, {y:.4f})")
    )

    panel.show()
    app.exec()


if __name__ == "__main__":
    main()
