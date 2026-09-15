import sys

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


class OutputPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QtWidgets.QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QtCore.QSize(16, 16))

        clear_action = toolbar.addAction("Clear")
        clear_action.triggered.connect(self.clear)

        copy_action = toolbar.addAction("Copy")
        copy_action.triggered.connect(self.copy)

        self.auto_scroll = toolbar.addAction("Auto Scroll")
        self.auto_scroll.setCheckable(True)
        self.auto_scroll.setChecked(True)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setUndoRedoEnabled(False)
        self.output.setMaximumBlockCount(10000)
        self.output.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        )

        layout.addWidget(toolbar)
        layout.addWidget(self.output, 1)

    @QtCore.pyqtSlot(str)
    def append_output(self, text):
        if not text:
            return

        cursor = QtGui.QTextCursor(self.output.document())
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(text)

        if self.auto_scroll.isChecked():
            self.output.setTextCursor(cursor)
            self.output.ensureCursorVisible()

    def clear(self):
        self.output.clear()

    def copy(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.output.toPlainText())


class OutputBridge(QtCore.QObject):
    output_written = QtCore.pyqtSignal(str)


class TeeOut:
    def __init__(self, stream, callback):
        self._stream = stream
        self._callback = callback

    def write(self, text):
        result = self._stream.write(text)

        try:
            self._callback(text)
        except RuntimeError:
            pass

        return result

    def flush(self):
        self._stream.flush()

    def isatty(self):
        return self._stream.isatty()

    def writable(self):
        return True

    @property
    def encoding(self):
        return self._stream.encoding

    @property
    def errors(self):
        return self._stream.errors

    def __getattr__(self, name):
        return getattr(self._stream, name)


class CaptureOutput:
    def __init__(self, panel):
        self._panel = panel
        self._bridge = OutputBridge(panel)
        self._bridge.output_written.connect(
            panel.append_output, QtCore.Qt.ConnectionType.QueuedConnection
        )

        self._original_stdout = None
        self._original_stderr = None
        self._stdout_tee = None
        self._stderr_tee = None

    def install(self):
        if self._stdout_tee is not None:
            return

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_tee = TeeOut(sys.stdout, self._bridge.output_written.emit)
        self._stderr_tee = TeeOut(sys.stderr, self._bridge.output_written.emit)
        sys.stdout = self._stdout_tee
        sys.stderr = self._stderr_tee

    def restore(self):
        if self._stdout_tee is None:
            return

        try:
            self._stdout_tee.flush()
            self._stderr_tee.flush()
        finally:
            if sys.stdout is self._stdout_tee:
                sys.stdout = self._original_stdout

            if sys.stderr is self._stderr_tee:
                sys.stderr = self._original_stderr

            self._stdout_tee = None
            self._stderr_tee = None
