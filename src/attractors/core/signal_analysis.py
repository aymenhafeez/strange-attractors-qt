# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass

import numpy as np
from scipy.signal import ShortTimeFFT, get_window, periodogram


@dataclass(frozen=True)
class SampledSignal:
    values: np.ndarray
    times: np.ndarray
    dt: float


def sample_times(t_min, t_max, n):
    return np.linspace(t_min, t_max, n + 1)[1:]


def trajectory_signal(solution, column, *, t_min, t_max):
    return SampledSignal(
        values=solution[:, column],
        times=sample_times(t_min, t_max, len(solution)),
        dt=(t_max - t_min) / len(solution),
    )


def prepare_signal(values, *, times=None, dt=None, t0=0.0):
    if (times is None) == (dt is None):
        raise ValueError("Supply exactly one of times or dt")

    values = np.asarray(values)

    if times is None:
        times = t0 + np.arange(values.size) * dt
    else:
        times = np.asarray(times, dtype=np.float64)
        if times.shape != values.shape:
            raise ValueError("Sample times must match the signal shape")

        dt = (times[-1] - times[0]) / (times.size - 1)

    return SampledSignal(values=values, times=times, dt=float(dt))


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
        raise ValueError("Select an interval containing at least two samples")

    return SampledSignal(
        values=signal.values[first:stop],
        times=signal.times[first:stop],
        dt=signal.dt,
    )


def power_spectral_density(signal, *, remove_mean=True, window="hann"):
    n = signal.values.size
    sample_rate = 1.0 / signal.dt
    weights = get_window(window, n, fftbins=True)
    frequencies, density = periodogram(
        signal.values,
        fs=sample_rate,
        window=weights,
        detrend="constant" if remove_mean else False,
        scaling="density",
    )

    return PowerSpectrum(
        frequencies=frequencies,
        density=density,
        bin_spacing=sample_rate / n,
        noise_bandwidth=float(sample_rate * np.sum(weights**2) / np.sum(weights) ** 2),
    )


@dataclass(frozen=True)
class Spectrogram:
    frequencies: np.ndarray
    times: np.ndarray
    density: np.ndarray
    window_samples: int
    hop_samples: int
    bin_spacing: float
    noise_bandwidth: float


def power_spectrogram(
    signal, *, window_duration, overlap=0.5, remove_mean=True, window="hann"
):
    window_samples = round(window_duration / signal.dt)
    if not 1 <= window_samples <= signal.values.size:
        raise ValueError(
            f"Window requires {window_samples:,} samples; "
            f"signal contains {signal.values.size:,}"
        )

    hop_samples = max(1, round(window_samples * (1.0 - overlap)))
    column_count = 1 + (signal.values.size - window_samples) // hop_samples
    sample_rate = 1.0 / signal.dt
    weights = get_window(window, window_samples, fftbins=True)

    transform = ShortTimeFFT(
        weights,
        hop=hop_samples,
        fs=sample_rate,
        fft_mode="onesided2X",
        mfft=window_samples,
        scale_to="psd",
    )

    offset = window_samples // 2
    density = transform.spectrogram(
        signal.values,
        detr="constant" if remove_mean else None,
        p0=0,
        p1=column_count,
        k_offset=offset,
        padding="zeros",
    )
    times = signal.times[0] + transform.t(
        signal.values.size, p0=0, p1=column_count, k_offset=offset
    )

    return Spectrogram(
        frequencies=transform.f,
        times=times,
        density=density,
        window_samples=window_samples,
        hop_samples=hop_samples,
        bin_spacing=transform.delta_f,
        noise_bandwidth=float(sample_rate * np.sum(weights**2) / np.sum(weights) ** 2),
    )
