# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

from pyqtgraph.Qt import QtCore, QtWidgets

from .process_metrics import ProcessUsageStatus

MESSAGE_COLOUR = "#178640"
ERROR_COLOUR = "#ff6b6b"


class AppStatusBar(QtWidgets.QStatusBar):
    def __init__(self, output_panel_action, visibility_action, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)

        self._app_message = ""
        self._app_error = False
        self._signal_message = ""
        self._signal_error = False
        self._temporary_message = None
        self._process_visible = True

        output_panel_button = QtWidgets.QToolButton()
        output_panel_button.setDefaultAction(output_panel_action)
        output_panel_button.setAutoRaise(True)
        output_panel_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        output_panel_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        output_panel_button.setToolTip("Toggle Output Panel")
        self.addWidget(output_panel_button)

        self.app_status_label = QtWidgets.QLabel("")
        self.app_status_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.app_status_label.setStyleSheet(
            f"border: none; padding: 0 4px 1px 4px; font-size: 12px; "
            f"color: {MESSAGE_COLOUR};"
        )
        self.process_status = ProcessUsageStatus()
        self.addWidget(self.app_status_label, 1)
        self.addPermanentWidget(self.process_status)
        self.process_status.set_active(True)

        self._clear_timer = QtCore.QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_temporary_message)

        self._visibility_action = visibility_action
        visibility_action.setChecked(True)
        visibility_action.toggled.connect(self.set_process_visible)

    @property
    def process_visible(self):
        return self._process_visible

    def set_process_visible(self, visible):
        self._process_visible = bool(visible)
        self.process_status.setVisible(self._process_visible)
        self.process_status.set_active(self._process_visible)

        with QtCore.QSignalBlocker(self._visibility_action):
            self._visibility_action.setChecked(self._process_visible)

        self._sync_visibility()

    def set_app_message(self, message, error=False):
        self._app_message = str(message)
        self._app_error = error
        self._refresh()

    def set_temporary_app_message(self, message, *, timeout_ms=3000, error=False):
        self.set_app_message(message, error=error)
        self._temporary_message = self._app_message
        self._clear_timer.start(int(timeout_ms))

    def clear_app_message(self):
        self.set_app_message("")

    def set_signal_message(self, message, error=False):
        self._signal_message = str(message)
        self._signal_error = error
        self._refresh()

    def _clear_temporary_message(self):
        # newer message replaces the temporary one and isn't cleared
        if self._app_message == self._temporary_message:
            self.clear_app_message()

    def _refresh(self):
        text = " · ".join(
            message for message in (self._app_message, self._signal_message) if message
        )
        has_error = (self._app_message and self._app_error) or (
            self._signal_message and self._signal_error
        )
        colour = ERROR_COLOUR if has_error else MESSAGE_COLOUR

        self.app_status_label.setText(text)
        self.app_status_label.setToolTip(text)
        self.app_status_label.setStyleSheet(
            f"border: none; padding: 0 4px 3px 4px; font-size: 12px; color: {colour};"
        )
        self._sync_visibility()

    def _sync_visibility(self):
        self.setVisible(
            bool(self._process_visible or self._app_message or self._signal_message)
        )
