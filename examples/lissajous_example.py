"""
Interactive example of a Lissajous curve.

a: x frequency controlling the number of oscillations in the x direction
b: y frequency controlling the number of oscillations in the y direction
phi: phase shift controlling the horizontal offset of the curve
"""

liss = plots.new("Lissajous")

t = np.arange(0, 2 * np.pi, 0.01)

a = liss.explore.slider("a", value=3.0, start=0.0, end=15, step=0.01)
b = liss.explore.slider("b", value=5.0, start=0.0, end=15, step=0.01)
phi = liss.explore.slider("phi", value=0.0, start=0.0, end=2 * np.pi, step=0.01)

# Bind values locally so later console assignments with the same names don't
# affect this plot
liss.explore.curve(
    "lissajous",
    lambda a=a, t=t, phi=phi: np.sin(a.value * t + phi.value),
    lambda b=b, t=t: np.sin(b.value * t),
)
