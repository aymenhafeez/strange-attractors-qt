"""
Animated parameter sweep of an iterative attractor


Redraw the plot as QTimer advances the parameter 'a'. The value gets reset to
its initial value when it reaches its end bound so run timer.stop() in the console
to pause the animation
"""

import gc

from numba import njit
from pyqtgraph.Qt.QtCore import QTimer

# disable garbage collection to stop periodic stuttering from repeated array allocation
# enable again with gc.enable() if continuing with the console session after this example
gc.disable()

line = plot(
    [],
    [],
    pen=None,
    symbol="o",
    symbolPen=None,
    symbolBrush="w",
    symbolSize=1,
    plot="Sweep",
)

# fix view range so bounds don't get recomputed every frame
pw = line.getViewBox().parentWidget()
pw.disableAutoRange()
pw.setXRange(-1.1, 1.1)
pw.setYRange(-1.1, 1.1)
# pw.showGrid(x=False, y=False)

a_start = -20
a_end = 20
a_current = a_start
step = 0.025
b = 1
n = 50000


@njit
def itr_attr(a, b, n):
    x = np.empty(n)
    y = np.empty(n)

    x_prev = 0.0
    y_prev = 0.0

    x[0] = x_prev
    y[0] = y_prev

    for i in range(1, n):
        x_new = np.sin(x_prev**2 - y_prev**2 + a)
        y_new = np.cos(2 * x_prev * y_prev + b)

        x[i] = x_new
        y[i] = y_new

        x_prev = x_new
        y_prev = y_new

    return x, y


def update():
    global step, a_current

    x, y = itr_attr(a_current, b, n)
    line.setData(x, y)
    a_current += step

    if a_current >= a_end:
        a_current = a_start


timer = QTimer()
timer.timeout.connect(update)
timer.start(16)
