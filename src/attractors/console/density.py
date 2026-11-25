# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numpy as np


def check_bins2d(bins):
    if np.isscalar(bins):
        bins = (bins, bins)

    nx, ny = (int(n) for n in bins)
    if nx < 1 or ny < 1:
        raise ValueError("bins must be at least 1")

    return nx, ny


def check_extent(extent):
    x0, x1, y0, y1 = (float(v) for v in extent)
    if not (x0 < x1 and y0 < y1):
        raise ValueError("extent must be (x0, x1, y0, y1) with x1 > x0 and y1 > y0")

    return x0, x1, y0, y1


def check_image(values):
    data = np.asarray(values)
    if data.ndim != 2:
        raise ValueError("image must be two dimensional")

    return data


def auto_extent(x, y, pad=0.05):
    extent = []
    for values in (x, y):
        values = np.asarray(values)
        values = values[np.isfinite(values)]
        lo, hi = float(values.min()), float(values.max())
        margin = pad * (hi - lo) if hi > lo else 0.5
        extent += [lo - margin, hi + margin]

    return tuple(extent)


def bin_points(x, y, bins, extent):
    nx, ny = bins
    x0, x1, y0, y1 = extent
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    ix = ((x[inside] - x0) * (nx / (x1 - x0))).astype(np.int64)
    iy = ((y[inside] - y0) * (ny / (y1 - y0))).astype(np.int64)

    # put points on the right and top edges in the last bin
    np.minimum(ix, nx - 1, out=ix)
    np.minimum(iy, ny - 1, out=iy)

    return np.bincount(iy * nx + ix, minlength=nx * ny).reshape(ny, nx)


def tone_map(counts, scale="log", gamma=1.0):
    if scale not in ("linear", "log"):
        raise ValueError("scale must be 'linear' or 'log'")

    peak = counts.max()
    if peak == 0:
        return np.zeros(counts.shape, dtype=np.float32)

    if scale == "log":
        image = np.log1p(counts) / np.log1p(peak)
    else:
        image = counts / peak

    return (image ** (1.0 / gamma)).astype(np.float32)
