"""
Interactive de Jong attractor plot. Increasing the number of points will make the plot
more defined but will slow down render updates on slider ticks.

Interesting param combos:
a=-1.33, b=-2, c=-1.2, d=2.0
a=-2.55, b=-1.12, c=-1.47, d=2.75
a=1.82, b=-1.09, c=1.16, d=-2.05
"""

from numba import njit

dejong_plot = plots.new("Dejong")

a = dejong_plot.explore.slider("a", value=-2.0, start=-10.0, end=10.0, step=0.01)
b = dejong_plot.explore.slider("b", value=-2.0, start=-10.0, end=10.0, step=0.01)
c = dejong_plot.explore.slider("c", value=-1.2, start=-10.0, end=10.0, step=0.01)
d = dejong_plot.explore.slider("d", value=2.0, start=-10.0, end=10.0, step=0.01)

n = dejong_plot.explore.int_slider(
    "points", value=30000, start=1000, end=500000, step=1000
)


@njit
def dejong_points(a, b, c, d, n):
    x = np.empty(n)
    y = np.empty(n)
    x_prev = 0.0
    y_prev = 0.0
    x[0] = np.sin(a * y_prev) - np.cos(b * x_prev)
    y[0] = np.sin(c * x_prev) - np.cos(d * y_prev)

    for i in range(1, n):
        x_new = np.sin(a * y_prev) - np.cos(b * x_prev)
        y_new = np.sin(c * x_prev) - np.cos(d * y_prev)
        x[i] = x_new
        y[i] = y_new
        x_prev = x_new
        y_prev = y_new

    return x, y


# Bind values locally so later console assignments with the same names don't
# affect this plot
dejong_plot.explore.scatter(
    "de Jong attractor",
    lambda a=a, b=b, c=c, d=d, n=n: dejong_points(
        a.value, b.value, c.value, d.value, int(n.value)
    )[0],
    lambda a=a, b=b, c=c, d=d, n=n: dejong_points(
        a.value, b.value, c.value, d.value, int(n.value)
    )[1],
    pen=None,
    symbol="o",
    symbolSize=1,
    symbolPen=None,
    symbolBrush="white",
)
