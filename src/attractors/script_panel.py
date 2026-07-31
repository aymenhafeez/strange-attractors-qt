from pathlib import Path

from PyQt6.Qsci import QsciLexerPython, QsciScintilla
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from .script_browser import ScriptBrowser

# dark mode palette derived from KDE Breeze Dark
# https://www.riverbankcomputing.com/static/Docs/QScintilla/classQsciLexer.html
# https://lxr.kde.org/source/frameworks/syntax-highlighting/data/themes/breeze-dark.theme
EDITOR_BACKGROUND = "#232629"
EDITOR_TEXT = "#cfcfc2"
EDITOR_MARGIN = "#31363b"
EDITOR_MARGIN_TEXT = "#7a7c7d"
EDITOR_SELECTION = "#2d5c76"
EDITOR_CARET_LINE = "#2a2e32"

PYTHON_STYLE_COLOURS = {
    QsciLexerPython.ClassName: "#2980b9",
    QsciLexerPython.Comment: "#7a7c7d",
    QsciLexerPython.CommentBlock: "#7a7c7d",
    QsciLexerPython.Decorator: "#3f8058",
    QsciLexerPython.DoubleQuotedFString: "#da4453",
    QsciLexerPython.DoubleQuotedString: "#f44f4f",
    QsciLexerPython.FunctionMethodName: "#8e44ad",
    QsciLexerPython.HighlightedIdentifier: "#27aeae",
    QsciLexerPython.Identifier: EDITOR_TEXT,
    QsciLexerPython.Keyword: EDITOR_TEXT,
    QsciLexerPython.Number: "#f67400",
    QsciLexerPython.Operator: "#3f8058",
    QsciLexerPython.SingleQuotedFString: "#da4453",
    QsciLexerPython.SingleQuotedString: "#f44f4f",
    QsciLexerPython.TripleDoubleQuotedFString: "#da4453",
    QsciLexerPython.TripleDoubleQuotedString: "#da4453",
    QsciLexerPython.TripleSingleQuotedFString: "#da4453",
    QsciLexerPython.TripleSingleQuotedString: "#da4453",
    QsciLexerPython.UnclosedString: "#da4453",
}


def _is_dark_mode():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False

    style_hints = app.styleHints()
    colour_scheme = getattr(style_hints, "colorScheme", None)
    if colour_scheme is not None:
        scheme = colour_scheme()
        if scheme != QtCore.Qt.ColorScheme.Unknown:
            return scheme == QtCore.Qt.ColorScheme.Dark

    palette = app.palette()
    window = palette.color(QtGui.QPalette.ColorRole.Window)
    text = palette.color(QtGui.QPalette.ColorRole.WindowText)

    return window.lightness() < text.lightness()


def _default_scripts_dir():
    app_data = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    if app_data:
        return Path(app_data) / "scripts"

    return Path(QtCore.QDir.homePath()) / ".strange-attractors" / "scripts"


class ScriptStore:
    def __init__(self, root):
        self.root = Path(root) if root is not None else _default_scripts_dir()

    def ensure_root(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_script(self, path):
        path = Path(path).resolve()
        root = self.root.resolve()

        if root != path and root not in path.parents:
            raise ValueError(f"Script path {path} is outside of scripts directory")
        if path.suffix != ".py":
            raise ValueError("Script is not a Python file")

        return path

    def read(self, path):
        return self.resolve_script(path).read_text(encoding="utf-8")

    def write(self, path, text):
        path = self.resolve_script(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file = QtCore.QSaveFile(str(path))
        if not file.open(
            QtCore.QIODevice.OpenModeFlag.WriteOnly | QtCore.QIODevice.OpenModeFlag.Text
        ):
            raise OSError(file.errorString())

        file.write(text.encode("utf-8"))

        if not file.commit():
            raise OSError(file.errorString())


class ScriptPanel(QtWidgets.QWidget):
    run_requested = QtCore.pyqtSignal(str)
    status_changed = QtCore.pyqtSignal(str)
    script_changed = QtCore.pyqtSignal(object)

    def __init__(self, scripts_dir, parent=None):
        super().__init__(parent)
        self.store = ScriptStore(scripts_dir)
        self.scripts_dir = self.store.root
        self.script_path = self.scripts_dir / "scratch.py"
        self.current_path = None
        self._loading = False
        self._dirty = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.script_browser = ScriptBrowser(self.scripts_dir)
        self.script_browser.script_selected.connect(self.load_script)

        editor_host = QtWidgets.QWidget()
        editor_layout = QtWidgets.QVBoxLayout(editor_host)
        editor_layout.setContentsMargins(6, 6, 6, 6)
        editor_layout.setSpacing(6)

        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.run_action = self.toolbar.addAction("Run")
        self.run_action.setToolTip("Run script")
        self.save_action = self.toolbar.addAction("Save")
        self.save_action.setToolTip("Save script")

        self.status_label = QtWidgets.QLabel()
        self.status_label.setMinimumWidth(120)
        self.toolbar.addWidget(self.status_label)

        self.editor = QsciScintilla()
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        self.editor.setFont(font)
        self.editor.setMarginsFont(font)
        self.editor.setReadOnly(False)
        self.editor.setIndentationsUseTabs(False)
        self.editor.setTabWidth(4)
        self.editor.setIndentationWidth(4)
        self.editor.setAutoIndent(True)
        self.editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.editor.setCaretLineVisible(True)
        self.editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.editor.setMarginWidth(0, "0000")

        self.lexer = QsciLexerPython(self.editor)
        self.lexer.setDefaultFont(font)

        if _is_dark_mode():
            self._apply_dark_editor_colours()

        self.editor.setLexer(self.lexer)

        editor_layout.addWidget(self.toolbar)
        editor_layout.addWidget(self.editor, 1)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.script_browser)
        self.splitter.addWidget(editor_host)
        self.splitter.setSizes([220, 620])
        layout.addWidget(self.splitter)

        self.editor.textChanged.connect(self._on_editor_text_changed)

        self.run_action.triggered.connect(self.run)
        self.save_action.triggered.connect(self.save)

        self.load()

    def _apply_dark_editor_colours(self):
        self.editor.setCaretForegroundColor(QtGui.QColor(EDITOR_TEXT))
        self.editor.setCaretLineBackgroundColor(QtGui.QColor(EDITOR_CARET_LINE))
        self.editor.setColor(QtGui.QColor(EDITOR_TEXT))
        self.editor.setPaper(QtGui.QColor(EDITOR_BACKGROUND))
        self.editor.setSelectionBackgroundColor(QtGui.QColor(EDITOR_SELECTION))
        self.editor.setSelectionForegroundColor(QtGui.QColor(EDITOR_TEXT))
        self.editor.setMarginsBackgroundColor(QtGui.QColor(EDITOR_MARGIN))
        self.editor.setMarginsForegroundColor(QtGui.QColor(EDITOR_MARGIN_TEXT))
        self.lexer.setDefaultColor(QtGui.QColor(EDITOR_TEXT))
        self.lexer.setDefaultPaper(QtGui.QColor(EDITOR_BACKGROUND))

        for style, colour in PYTHON_STYLE_COLOURS.items():
            self.lexer.setColor(QtGui.QColor(colour), style)
            self.lexer.setPaper(QtGui.QColor(EDITOR_BACKGROUND), style)

    def load(self):
        self.store.ensure_root()

        if not self.script_path.exists():
            self.store.write(self.script_path, "")

        self.load_script(self.script_path)

    def load_script(self, path):
        path = self.store.resolve_script(path)

        if path == self.current_path:
            return True

        if not self._confirm_discard_changes():
            return False

        self._loading = True
        try:
            self.editor.setText(self.store.read(path))
            self.editor.setModified(False)

            self.current_path = path
            self._dirty = False

            self._update_status("Loaded")
            self.script_changed.emit(path)
            self.script_browser.select_script(path)
        finally:
            self._loading = False

        return True

    def save(self):
        if self.current_path is None:
            self.load()

        self.store.write(
            self.current_path,
            self.editor.text(),
        )

        self.editor.setModified(False)
        self._dirty = False
        self._update_status("Saved")

        return True

    def run(self):
        self.save()
        self.run_requested.emit(self.editor.text())
        self._update_status("Ran")

    def _on_editor_text_changed(self):
        if self._loading:
            return

        self._dirty = True
        self._update_status("Modified")

    def _confirm_discard_changes(self):
        if not self._dirty:
            return True

        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved script",
            "Discard unsaved script changes?",
            QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )

        return result == QtWidgets.QMessageBox.StandardButton.Discard

    def _update_status(self, action):
        if self.current_path is None:
            self.status_label.clear()
            self.status_changed.emit("")
            return

        if self._dirty:
            self.status_label.setText(f"Modified {self.current_path.name}")
        else:
            self.status_label.clear()

        if action != "Modified":
            self.status_changed.emit(f"{action} {self.current_path.name}")
