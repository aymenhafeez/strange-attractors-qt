"""
Example usage for plotting methods

curve()   : trace plot
scatter() : trace with "o" symbol
hist()    : step curve to show binned distribution
hline()   : horizontal line with specified y value
vline()   : vertical line with specified x value
"""

p = plots.new("Distribution")

mean = p.explore.slider("mean", 0.0, -3.0, 3.0, 0.1)
std = p.explore.slider("std", 1.0, 0.2, 2.0, 0.1)
bins = p.explore.int_slider("bins", 40, 10, 100, 1)

# fixed random samples so changing parameters transforms the same data
rng = np.random.default_rng(42)
z = rng.normal(size=2000)


def samples():
    return mean.value + std.value * z


def gaussian_x():
    return np.linspace(
        mean.value - 4 * std.value,
        mean.value + 4 * std.value,
        300,
    )


def gaussian_y():
    x = gaussian_x()
    return (
        1
        / (std.value * np.sqrt(2 * np.pi))
        * np.exp(-0.5 * ((x - mean.value) / std.value) ** 2)
    )


p.explore.hist(
    "sample distribution",
    samples,
    bins=lambda bins=bins: int(bins.value),
    density=True,
)

p.explore.curve(
    "expected distribution",
    gaussian_x,
    gaussian_y,
    pen="yellow",
    mode="overlay",
)

p.explore.scatter(
    "sample values",
    lambda: samples()[:30],
    lambda: np.full(30, -0.025),
    size=6,
    mode="overlay",
)

p.explore.vline(
    "mean",
    lambda mean=mean: mean.value,
    pen="cyan",
)

p.explore.hline(
    "peak density",
    lambda std=std: 1 / (std.value * np.sqrt(2 * np.pi)),
    pen="orange",
)
