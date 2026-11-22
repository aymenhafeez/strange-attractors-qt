"""Density example showing the logistic map x -> r x (1 - x) as a bifurcation diagram

For plots where millions of points need to be shown, binning the points into a density
better shows the behaviour around the band edges and period windows as apposed to a
standard scatter plot
"""

import numpy as np
from numba import njit

@njit
def logistic_points(r_from, r_to, n_r, n_keep):
    rs = np.empty(n_r * n_keep)
    xs = np.empty(n_r * n_keep)

    for i in range(n_r):
        r = r_from + (r_to - r_from) * i / (n_r - 1)
        x = 0.5
        # skip transient so only the long term behaviour is binned
        for _ in range(1000):
            x = r * x * (1 - x)
        for j in range(n_keep):
            x = r * x * (1 - x)
            rs[i * n_keep + j] = r
            xs[i * n_keep + j] = x

    return rs, xs


logistic_plot = plots.new("Logistic map")
r_from = logistic_plot.explore.slider(
    "r from", value=2.8, start=2.5, end=4.0, step=0.001
)
r_to = logistic_plot.explore.slider("r to", value=4.0, start=2.5, end=4.0,
step=0.001)


# bind values locally so later console assignments with the same names don't
# affect this plot
def points(r_from=r_from, r_to=r_to):
    return logistic_points(r_from.value, r_to.value, 2000, 500)


logistic_plot.explore.density(
    "logistic map",
    lambda: points()[0],
    lambda: points()[1],
    bins=(800, 500),
)
