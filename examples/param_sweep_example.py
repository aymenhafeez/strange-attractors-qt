import gc

import numpy as np
from numba import njit

# disable garbage collection to stop periodic stuttering from repeated array allocation
# enable again with gc.enable() if continuing with the console session after this example
gc.disable()

attr = plots.new("Param sweep")

item = attr.line(
    [],
    [],
    pen=None,
    symbol="o",
    symbolPen=None,
    symbolBrush="w",
    symbolSize=1,
)

# fix view range so bounds don't get recomputed every frame
pw = item.getViewBox().parentWidget()
pw.disableAutoRange()
pw.setXRange(-1.1, 1.1)
pw.setYRange(-1.1, 1.1)
# pw.showGrid(x=False, y=False)


@njit
def attractor(a, b, n):
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


a_start = -20
a_end = 20
b = 1
step = 0.01
n = 20000


# use anim.frame, anim.time, anim.dt in animation callbacks
# bind callback inputs so other console scripts don't overwrite them
def update(
    anim,
    item=item,
    attractor=attractor,
    a_start=a_start,
    a_end=a_end,
    b=b,
    n=n,
    step=step,
):
    anim_span = a_end - a_start
    a = a_start + (step * anim.frame) % anim_span
    x, y = attractor(a, b, n)
    item.setData(x, y)


attr.explore.animation("Param sweep", callback=update, start=True)
