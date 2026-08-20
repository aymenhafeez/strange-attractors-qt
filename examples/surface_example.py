"""Interactive surface plot"""

v = views3d.new("Reactive surface test")
v.clear()

amp = v.explore.slider("amplitude", value=1.0, start=0.0, end=3.0, step=0.01)
freq = v.explore.slider("frequency", value=2.0, start=0.2, end=8.0, step=0.01)
phase = v.explore.slider("phase", value=0.0, start=0.0, end=2 * np.pi, step=0.01)

x = np.linspace(-4, 4, 100)
y = np.linspace(-4, 4, 100)
X, Y = np.meshgrid(x, y)


def surface(amp=amp, freq=freq, phase=phase, X=X, Y=Y):
    r = np.sqrt(X**2 + Y**2)
    return amp.value * np.sin(freq.value * r + phase.value)


v.explore.surface3d(
    "ripples",
    x,
    y,
    surface,
    colour=(0.2, 0.7, 1.0, 1.0),
)

v.explore.wireframe3d(
    "grid",
    x,
    y,
    surface,
    colour=(1.0, 1.0, 1.0, 0.35),
    width=1,
    mode="overlay",
)
