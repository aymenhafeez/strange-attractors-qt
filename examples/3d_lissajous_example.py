"""Interactive plot of the Lissajous curve lifted into 3D

a and b control the oscillation frequencies in the x and y directions.
"""

v = views3d.new("Lissajous helix")

a = v.explore.slider("a", value=1, start=0.0, end=5, step=0.01)
b = v.explore.slider("b", value=1, start=0.0, end=5, step=0.01)
s = v.explore.slider("size", value=25, start=1, end=50, step=1)

t = np.linspace(0, 8 * np.pi, 2000)


def points(a=a, b=b, t=t):
    return np.column_stack(
        [
            np.sin(a.value * t),
            np.cos(b.value * t),
            t / 10,
        ]
    )


def colours(a=a, b=b, t=t, cmap=cmap):
    values = np.sin(a.value * t) + np.cos(b.value * t)
    return colourmap(values, cmap="magam")


def sample_points(points=points):
    return points()[::50]


def sample_colours(colours=colours):
    return colours()[::50]


v.explore.line3d(
    "helix",
    points,
    colour=colours,
    width=3,
)

v.explore.scatter3d(
    "helix samples",
    sample_points,
    colour=sample_colours,
    mode="overlay",
    size=lambda s=s: s.value,
)
