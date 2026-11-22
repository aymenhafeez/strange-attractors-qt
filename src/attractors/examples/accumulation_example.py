"""Accumulation example showing the Barnsley fern

`accumulate()` is good for visualising structures like this where tens of thousands of
points are required to show the full detail of the shape
"""

import numpy as np
from numba import njit


@njit(nogil=True)
def fern_chunk(x, y, n):
    xs = np.empty(n)
    ys = np.empty(n)

    for i in range(n):
        r = np.random.random()
        if r < 0.01:
            x, y = 0.0, 0.16 * y
        elif r < 0.86:
            x, y = 0.85 * x + 0.04 * y, -0.04 * x + 0.85 * y + 1.6
        elif r < 0.93:
            x, y = 0.2 * x - 0.26 * y, 0.23 * x + 0.22 * y + 1.6
        else:
            x, y = -0.15 * x + 0.28 * y, 0.26 * x + 0.24 * y + 0.44
        xs[i] = x
        ys[i] = y

    return xs, ys


def fern_chunks():
    x = y = 0.0
    while True:
        xs, ys = fern_chunk(x, y, 500_000)
        x, y = xs[-1], ys[-1]
        yield xs, ys


fern_plot = plots.new("Fern")

# match binds to extent aspect ratio so pixels stay square
fern_plot.explore.accumulate(
    "fern",
    fern_chunks,
    bins=(550, 1000),
    extent=(-2.75, 2.75, 0.0, 10.0),
    cmap="viridis",
    max_points=200_000_000,
)

