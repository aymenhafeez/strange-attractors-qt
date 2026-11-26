# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets


@dataclass(frozen=True)
class Kind:
    label: str
    view: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int


@dataclass
class SliderItem:
    name: str
    value: float = 1.0
    start: float = -10.0
    end: float = 10.0
    step: float = 0.01


@dataclass
class TraceItem:
    kind: str
    name: str
    expressions: dict[str, str]
    ranges: dict[str, tuple[float, float]]
    samples: int
    # colour or cmap name
    style: str


