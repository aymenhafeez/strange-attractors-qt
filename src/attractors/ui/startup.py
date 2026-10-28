# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtWidgets


class WelcomeDialog(QtWidgets.QDialog):
    system_requested = QtCore.pyqtSignal()
    example_requested = QtCore.pyqtSignal()
    help_requested = QtCore.pyqtSignal()

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("System analysis")
        self.resize(460, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        heading = QtWidgets.QLabel("Welcome to Systems analysis")
        font = heading.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        description = QtWidgets.QLabel(
            "Visualise dynamical systems, analyse their behaviour, "
            "or build your own plots with Python."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        for text, signal in (
            ("Explore a system", self.system_requested),
            ("Try a scripting example", self.example_requested),
            ("Quick start", self.help_requested),
        ):
            button = QtWidgets.QPushButton(text)
            button.setMinimumHeight(36)
            button.setAutoDefault(False)
            button.clicked.connect(self.accept)
            button.clicked.connect(signal.emit)
            layout.addWidget(button)

        hint = QtWidgets.QLabel(
            "You can reopen this screen from <i>File</i> → <i>Welcome</i>."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        show_on_startup = QtWidgets.QCheckBox("Show on startup")
        show_on_startup.setChecked(
            settings.value("startup/show_welcome", True, type=bool)
        )
        show_on_startup.toggled.connect(
            lambda checked: settings.setValue("startup/show_welcome", checked)
        )
        layout.addWidget(show_on_startup)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
