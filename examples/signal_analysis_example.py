"""Interactive signal analysis

Frequency, noise, and smoothing controls update the signal plot, spectrum plot,
and summary metrics table
"""

rng = np.random.default_rng(4)

signal_plot = plots.new("Signal")
spectrum_plot = plots.new("Spectrum")
metrics_table = tables.new("Signal metrics")

frequency = signal_plot.explore.slider(
    "frequency", value=5.0, start=0.5, end=50.0, step=0.1
)
noise = signal_plot.explore.slider("noise", value=0.15, start=0.0, end=1.0, step=0.01)
window = signal_plot.explore.int_slider("window", value=21, start=3, end=151, step=2)

sample_rate = 500
duration = 2.0
t = np.arange(0, duration, 1 / sample_rate)
# fixed noise so the slider movements are comparable
base_noise = rng.normal(size=len(t))


def signal(frequency=frequency, noise=noise, t=t, base_noise=base_noise):
    clean = np.sin(2 * np.pi * frequency.value * t)
    harmonic = 0.35 * np.sin(2 * np.pi * 2.4 * frequency.value * t + 0.6)
    return clean + harmonic + noise.value * base_noise


def smoothed_signal(window=window):
    values = signal()
    n = max(3, int(window.value))
    if n % 2 == 0:
        n += 1

    kernel = np.ones(n) / n
    return np.convolve(values, kernel, mode="same")


def spectrum(sample_rate=sample_rate):
    values = signal()
    values = values - values.mean()
    frequencies = np.fft.rfftfreq(len(values), d=1 / sample_rate)
    power = np.abs(np.fft.rfft(values)) ** 2
    return frequencies, power


def dominant_frequency():
    frequencies, power = spectrum()
    if len(power) <= 1:
        return 0.0

    index = np.argmax(power[1:]) + 1
    return frequencies[index]


def metrics():
    values = signal()
    smooth = smoothed_signal()
    frequencies, power = spectrum()

    return pd.Series(
        {
            "mean": values.mean(),
            "std": values.std(),
            "min": values.min(),
            "max": values.max(),
            "dominant_frequency": dominant_frequency(),
            "total_power": power.sum(),
            "smoothing_window": int(window.value),
            "samples": len(values),
        }
    )


def refresh_metrics():
    metrics_table.set_data(metrics())


signal_plot.explore.curve("raw", lambda t=t: t, signal, pen="c")
signal_plot.explore.curve(
    "smooth", lambda t=t: t, smoothed_signal, pen="y", mode="overlay", zoom_region=True
)
signal_plot.set_labels(bottom="time", left="amplitude")

spectrum_plot.explore.curve(
    "power",
    lambda: spectrum()[0],
    lambda: spectrum()[1],
    pen="m",
)
spectrum_plot.explore.vline("dominant", dominant_frequency, pen="y")
spectrum_plot.set_labels(bottom="frequency", left="power")

# tables are static so update them when the controls change
frequency.changed.connect(refresh_metrics)
noise.changed.connect(refresh_metrics)
window.changed.connect(refresh_metrics)
refresh_metrics()

tables.show(workspace.views(), name="Workspace views")
