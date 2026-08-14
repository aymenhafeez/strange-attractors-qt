"""
Interactive Fourier series approximation of a square wave

terms: number of odd sine harmonics used in the approximation
"""

fourier = plots.new("fourier")

terms = fourier.explore.slider("terms", value=5, start=1, end=100, step=1)

x = lambda: np.linspace(-2 * np.pi, 2 * np.pi, 2000)


def square(x=x, terms=terms):
    x_vals = x()
    y = np.zeros_like(x_vals)
    for n in range(terms.value):
        k = 2 * n + 1
        y += np.sin(k * x_vals) / k
    return 4 / np.pi * y


# Bind values locally so later console assignments with the same names don't
# affect this plot
fourier.explore.curve(
    "Ideal",
    lambda x=x: x(),
    lambda x=x: np.sign(np.sin(x())),
    pen="blue",
    zoom_region=True,
)
fourier.explore.curve(
    "Square wave",
    lambda x=x: x(),
    lambda square=square: square(),
    pen="red",
    mode="overlay",
)
