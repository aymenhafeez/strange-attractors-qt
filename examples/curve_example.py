"""Example of a simple reactive curve plot"""

s = plots.new("sin and cos")

a = s.explore.slider("a", value=1.0, start=0.0, end=10.0, step=0.01)
b = s.explore.slider("b", value=1.0, start=0.0, end=10.0, step=0.01)

x = np.linspace(0, 6 * np.pi, 500)

# Bind values locally so later console assignments with the same names don't
# affect this plot
s.explore.curve(
    "sin", lambda x=x: x, lambda x=x, a=a: np.sin(a.value * x), pen="orange"
)
s.explore.curve(
    "cos",
    lambda x=x: x,
    lambda x=x, b=b: np.cos(b.value * x),
    pen="blue",
    # plot on top of the sin curve instead of replacing it
    mode="overlay",
)
