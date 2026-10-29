# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from functools import cache
from pathlib import Path

from PyQt6.QtSvg import QSvgRenderer
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .style import is_dark_mode


class _SvgIcon(QtGui.QIconEngine):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def clone(self):
        return _SvgIcon(self.data)

    def paint(self, painter, rect, mode, state):
        palette = QtWidgets.QApplication.palette()
        group = (
            QtGui.QPalette.ColorGroup.Disabled
            if mode == QtGui.QIcon.Mode.Disabled
            else QtGui.QPalette.ColorGroup.Active
        )

        role = (
            QtGui.QPalette.ColorRole.HighlightedText
            if mode == QtGui.QIcon.Mode.Selected
            else QtGui.QPalette.ColorRole.ButtonText
        )

        colour = palette.color(group, role).name().encode()
        # data = self.data.replace(b"#232629", colour).replace(b"#da4453", colour)
        data = self.data.replace(b"#232629", colour).replace(b"#da4453", colour)

        if mode in (QtGui.QIcon.Mode.Disabled, QtGui.QIcon.Mode.Selected):
            data = data.replace(b"#476478", colour)
        elif is_dark_mode():
            data = data.replace(b"#476478", b"#e8eaec")
        else:
            data = data.replace(b"#476478", b"#202326")

        QSvgRenderer(data).render(painter, QtCore.QRectF(rect))

    def pixmap(self, size, mode, state):
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)

        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()

        return pixmap


@cache
def icon(name):
    data = (Path(__file__).with_name("icons") / f"{name}.svg").read_bytes()
    return QtGui.QIcon(_SvgIcon(data))
