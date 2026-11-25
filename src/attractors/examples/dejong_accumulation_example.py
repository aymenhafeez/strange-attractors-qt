"""Accumulation example showing the de Jong attractor

While the de Jong attractor is used in another example showing slider control in a
standard scatter plot, accumulate() can be used to generate a much more detailed image
of it. The sliders work the same except each slider tick restarts the accumulation
"""

from numba import njit
import numpy as np

dejong_plot = plots.new("de Jong density")
a = dejong_plot.explore.slider("a", value=-1.18, start=-10.0, end=10.0, step=0.01)
b = dejong_plot.explore.slider("b", value=1.7, start=-10.0, end=10.0, step=0.01)
c = dejong_plot.explore.slider("c", value=1.6, start=-10.0, end=10.0, step=0.01)
d = dejong_plot.explore.slider("d", value=1.38, start=-10.0, end=10.0, step=0.01)


@njit(nogil=True)
def dejong(a, b, c, d, x, y, n):
    xs = np.empty(n)
    ys = np.empty(n)

    for i in range(n):
        x = np.sin(a * y) - np.cos(b * x)
        y = np.sin(c * x) - np.cos(d * y)
        xs[i] = x
        ys[i] = y

    return xs, ys


def dejong_chunks(dejong=dejong, a=a, b=b, c=c, d=d):
    params = a.value, b.value, c.value, d.value
    x = y = 0.0
    while True:
        xs, ys = dejong(*params, x, y, 500_000)
        x, y = xs[-1], ys[-1]
        yield xs, ys


dejong_plot.explore.accumulate(
    "de Jong", dejong_chunks, bins=2000, extent=(-2.1, 2.1, -2.1, 2.1)
)
