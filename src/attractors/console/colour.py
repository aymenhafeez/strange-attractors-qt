import numpy as np
import pyqtgraph as pg


def colourmap(values, cmap="viridis", *, alpha=1.0, vmin=None, vmax=None):
    values = _check_values(values)
    alpha = _check_alpha(alpha)

    if vmin is None:
        vmin = float(values.min())
    else:
        vmin = float(vmin)

    if vmax is None:
        vmax = float(values.max())
    else:
        vmax = float(vmax)

    if not np.isfinite(vmin) or not np.isfinite(vmax):
        raise ValueError("Colour limits must be finite")
    if vmax < vmin:
        raise ValueError("vmax must be greater than or equal to vmin")

    if vmax == vmin:
        normalised = np.full(values.shape, 0.5, dtype=np.float64)
    else:
        normalised = (values - vmin) / (vmax - vmin)
        normalised = np.clip(normalised, 0.0, 1.0)

    colours = pg.colormap.get(cmap, source="matplotlib").map(normalised, mode="float")
    colours = np.asarray(colours)

    if colours.shape[1] == 3:
        colours = np.column_stack(
            [colours, np.full(len(colours), alpha, dtype=np.float64)]
        )
    else:
        colours[:, 3] *= alpha

    return colours


def _check_values(values):
    data = np.asarray(values, dtype=np.float64)

    if data.ndim != 1:
        raise ValueError("Colour values must be 1D")
    if len(data) == 0:
        raise ValueError("Colours values can't be empty")
    if not np.all(np.isfinite(data)):
        raise ValueError("Colour values can't contain non finite values")

    return data


def _check_alpha(alpha):
    if not np.isfinite(alpha):
        raise ValueError("Alpha must be finite")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("Alpha must be between 0 and 1")

    return alpha
