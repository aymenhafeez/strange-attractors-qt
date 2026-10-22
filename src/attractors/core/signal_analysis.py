# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass

import numpy as np
from scipy.signal import get_window, periodogram


@dataclass(frozen=True)
class SampledSignal:
    values: np.ndarray
    times: np.ndarray
    dt: float


@dataclass(frozen=True)
class PowerSpectrum:
    frequencies: np.ndarray
    density: np.ndarray
    bin_spacing: float
    noise_bandwidth: float


def select_interval(signal, start, end):
    first = np.searchsorted(signal.times, start, side="left")
    stop = np.searchsorted(signal.times, end, side="right")
    if stop - first < 2:
        raise ValueError("Selected interval must contain atleast two samples")

    return SampledSignal(
        values=signal.values[first:stop], times=signal.times[first:stop], dt=signal.dt
    )


def power_spectral_density(signal, *, remove_mean=True, window="hann"):
    n = signal.values.size
    if n < 4:
        raise ValueError("Spectrum analysis requires at least four samples")
    if window not in ("hann", "boxcar"):
        raise ValueError(
            "Window must be either 'hann' or 'boxcar' (rectangular window)"
        )

    sample_rate = 1.0 / signal.dt
    weights = get_window(window, n, fftbins=True)
    frequencies, density = periodogram(
        signal.values,
        fs=sample_rate,
        window=weights,
        detrend="constant" if remove_mean else False,
        return_onesided=True,
        scaling="density",
    )

    if not np.all(np.isfinite(density)):
        raise ValueError("Spectrum calculation prodcued nonfinite power")

    return PowerSpectrum(
        frequencies=frequencies,
        density=density,
        bin_spacing=sample_rate / n,
        noise_bandwidth=float(sample_rate * np.sum(weights**2) / np.sum(weights) ** 2),
    )
