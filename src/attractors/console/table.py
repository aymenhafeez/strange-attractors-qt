import numpy as np
import pandas as pd


def normalise_table_data(data):
    if isinstance(data, pd.DataFrame):
        return data.copy()

    if isinstance(data, pd.Series):
        name = data.name if data.name is not None else "value"
        return data.rename(name).to_frame()

    if isinstance(data, dict):
        return _noramlise_mapping(data)

    if np.isscalar(data):
        return pd.DataFrame({"value": [data]})

    rows = _record_rows(data)
    if rows is not None:
        return pd.DataFrame(rows)

    array = np.asarray(data, dtype="object")

    if array.ndim == 0:
        return pd.DataFrame({"value": [array.item()]})

    if array.ndim == 1:
        return pd.DataFrame({"value": array})

    if array.ndim == 2:
        columns = [str(i) for i in range(array.shape[1])]
        return pd.DataFrame(array, columns=columns)

    raise ValueError("Table data must be scaler, 1D or 2D")


def _record_rows(data):
    if isinstance(data, (str, bytes)):
        return None

    try:
        rows = list(data)
    except TypeError:
        return None

    if rows and all(isinstance(row, dict) for row in rows):
        return rows

    return None


def _noramlise_mapping(data):
    if not data:
        return pd.DataFrame()

    try:
        return pd.DataFrame(data)

    except ValueError:
        return pd.DataFrame({"value": data})
