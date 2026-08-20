import numpy as np
import pandas as pd


def _1d_array(values, name, *, min_length=1):
    values = np.asarray(values)

    if values.ndim != 1:
        raise ValueError(f"{name} must be one dimensional")
    if len(values) < min_length:
        raise ValueError(f"{name} must have at least {min_length} values")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} can't contain non finite values")

    return values


def _1d_summary(values, name):
    data = np.asarray(values)
    if data.ndim != 1:
        raise ValueError(f"{name} must be one dimensional")

    finite = data[np.isfinite(data)]

    row = {
        "name": name,
        "count": len(data),
        "finite_count": len(finite),
        "missing_count": int(np.count_nonzero(~np.isfinite(data))),
    }

    if len(finite) == 0:
        row.update(
            {
                "mean": np.nan,
                "std": np.nan,
                "min": np.nan,
                "median": np.nan,
                "max": np.nan,
            }
        )
        return row

    row.update(
        {
            "mean": np.mean(finite),
            "std": np.std(finite),
            "min": np.min(finite),
            "median": np.median(finite),
            "max": np.max(finite),
        }
    )

    return row


def derivative(y, x=None):
    y_data = _1d_array(y, "y", min_length=2)
    if x is None:
        return np.gradient(y_data)

    x_data = _1d_array(x, "x", min_length=2)
    if len(x_data) != len(y_data):
        raise ValueError("x and y must be the same length")
    return np.gradient(y_data, x_data)


def integral(y, x=None, *, initial=0.0):
    y_data = _1d_array(y, "y")
    if x is None:
        dx = np.ones(len(y_data) - 1)
    else:
        x_data = _1d_array(x, "x")
        if len(x_data) != len(y_data):
            raise ValueError("x and y must be the same length")
        dx = np.diff(x_data)

    areas = 0.5 * (y_data[:-1] + y_data[1:]) * dx

    return np.concatenate([[initial], initial + np.cumsum(areas)])


def fit_line(x, y):
    x_data = _1d_array(x, "x", min_length=2)
    y_data = _1d_array(y, "y", min_length=2)
    if len(x_data) != len(y_data):
        raise ValueError("x and y must be the same length")
    if len(np.unique(x_data)) < 2:
        raise ValueError("x must contain at least two unique values")

    slope, intercept = np.polyfit(x_data, y_data, deg=1)
    fitted = slope * x_data + intercept
    residuals = y_data - fitted
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y_data - y_data.mean()) ** 2)
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    rmse = np.sqrt(np.mean(residuals**2))

    return pd.Series({"slope": slope, "intercept": intercept, "r2": r2, "rmse": rmse})


def summary(data):
    if isinstance(data, pd.DataFrame):
        rows = []
        for column in data.columns:
            row = _1d_summary(data[column].to_numpy(), column)
            rows.append(row)
        return pd.DataFrame(rows)

    if isinstance(data, pd.Series):
        name = "value" if data.name is None else data.name
        return pd.Series(_1d_summary(data.to_numpy(), name)).drop(labels=["name"])

    return pd.Series(_1d_summary(data, "value")).drop(labels=["name"])
