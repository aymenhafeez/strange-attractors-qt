from pathlib import Path

from PyQt6.Qsci import QsciLexerPython, QsciScintilla
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.style import SPLITTER_HANDLE_HOVER, is_dark_mode
from .script_browser import ScriptBrowser, default_scripts_dir

# dark mode palette derived from KDE Breeze Dark
# https://qscintilla.com/#syntax_highlighting/custom_lexer_example
# https://lxr.kde.org/source/frameworks/syntax-highlighting/data/themes/breeze-dark.theme
EDITOR_BACKGROUND = "#121416"
EDITOR_TEXT = "#EEEEEE"
EDITOR_MARGIN = "#1b1f22"
EDITOR_MARGIN_TEXT = "#B0BEC5"
EDITOR_SELECTION = "#244559"
EDITOR_CARET_LINE = "#1a1d20"

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


class ScriptStore:
    def __init__(self, root):
        self.root = Path(root) if root is not None else default_scripts_dir()

    def ensure_root(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.ensure_examples()

    def ensure_examples(self):
        source = Path(__file__).resolve().parents[3] / "examples"

        target = self.root / "examples"

        if not source.exists():
            return

        target.mkdir(exist_ok=True)

        for path in source.glob("*.py"):
            target_path = target / path.name
            if not target_path.exists():
                target_path.write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8"
                )

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
        self._script_browser_width = 220

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.script_browser = ScriptBrowser(self.scripts_dir)
        self.script_browser.script_selected.connect(self.load_script)
        self.script_browser.path_renamed.connect(self._on_path_renamed)
        self.script_browser.path_deleted.connect(self._on_path_deleted)

        editor_host = QtWidgets.QWidget()
        editor_layout = QtWidgets.QVBoxLayout(editor_host)
        editor_layout.setContentsMargins(6, 6, 6, 6)
        editor_layout.setSpacing(6)

        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
        self.toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.toggle_browser_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("view-list-tree"),
            "Files",
        )
        self.toggle_browser_action.setCheckable(True)
        self.toggle_browser_action.setChecked(True)
        self.toggle_browser_action.setToolTip("Show file browser")
        self.toggle_browser_action.toggled.connect(self._set_script_browser_visible)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.toolbar.addWidget(spacer)

        self.status_label = QtWidgets.QLabel()
        self.toolbar.addWidget(self.status_label)

        self.run_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("system-run"), "Run"
        )
        self.run_action.setToolTip("Run script")
        self.save_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("document-save"), "Save"
        )
        self.save_action.setToolTip("Save script")

        self.editor = self._build_editor()

        editor_layout.addWidget(self.toolbar)
        editor_layout.addWidget(self.editor, 1)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.script_browser)
        self.splitter.addWidget(editor_host)
        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([170, 620])
        # self.splitter.setContentsMargins(0, 0, 0, 0)
        self.splitter.setStyleSheet(SPLITTER_HANDLE_HOVER)
        layout.addWidget(self.splitter)

        self.editor.textChanged.connect(self._on_editor_text_changed)

        self.run_action.triggered.connect(self.run)
        self.save_action.triggered.connect(self.save)

        self.load()

    def example_scripts(self):
        examples_dir = self.scripts_dir / "examples"
        if not examples_dir.exists():
            return []

        return sorted(examples_dir.glob("*.py"), key=lambda p: p.name.lower())

    def _renamed_current_path(self, old_path, new_path):
        if self.current_path is None:
            return None

        old_path = Path(old_path).resolve()
        new_path = Path(new_path).resolve()
        current_path = self.current_path.resolve()

        if current_path == old_path:
            return new_path

        if old_path in current_path.parents:
            return new_path / current_path.relative_to(old_path)

        return None

    def _on_path_renamed(self, old_path, new_path):
        renamed_path = self._renamed_current_path(old_path, new_path)
        if renamed_path is None:
            return
        self.current_path = renamed_path
        self._update_status("Renamed")
        self.script_changed.emit(renamed_path)
        self.script_browser.select_path(renamed_path)

    def _on_path_deleted(self, path):
        if self.current_path is None:
            return

        if not self._check_match(path, self.current_path):
            return

        self.current_path = None
        self._dirty = False
        self._loading = True
        try:
            self._set_editor_text("")
            self._set_editor_modified(False)
        finally:
            self._loading = False
        self._update_status("")

        if not self.script_path.exists():
            self.store.write(self.script_path, "")

        self.load_script(self.script_path)

    def _check_match(self, parent, child):
        parent = Path(parent).resolve()
        child = Path(child).resolve()

        return child == parent or parent in child.parents

    def _apply_dark_editor_colours(self, editor):
        editor.setCaretForegroundColor(QtGui.QColor(EDITOR_TEXT))
        editor.setCaretLineBackgroundColor(QtGui.QColor(EDITOR_CARET_LINE))
        editor.setColor(QtGui.QColor(EDITOR_TEXT))
        editor.setPaper(QtGui.QColor(EDITOR_BACKGROUND))
        editor.setSelectionBackgroundColor(QtGui.QColor(EDITOR_SELECTION))
        editor.setSelectionForegroundColor(QtGui.QColor(EDITOR_TEXT))
        editor.setMarginsBackgroundColor(QtGui.QColor(EDITOR_MARGIN))
        editor.setMarginsForegroundColor(QtGui.QColor(EDITOR_MARGIN_TEXT))
        self.lexer.setDefaultColor(QtGui.QColor(EDITOR_TEXT))
        self.lexer.setDefaultPaper(QtGui.QColor(EDITOR_BACKGROUND))

        for style, colour in PYTHON_STYLE_COLOURS.items():
            self.lexer.setColor(QtGui.QColor(colour), style)
            self.lexer.setPaper(QtGui.QColor(EDITOR_BACKGROUND), style)

    def _build_editor(self):
        editor = QsciScintilla()
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        editor.setFont(font)
        editor.setMarginsFont(font)
        editor.setReadOnly(False)
        editor.setIndentationsUseTabs(False)
        editor.setTabWidth(4)
        editor.setIndentationWidth(4)
        editor.setAutoIndent(True)
        editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        editor.setCaretLineVisible(True)
        editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        editor.setMarginWidth(0, "0000")

        self.lexer = QsciLexerPython(editor)
        self.lexer.setDefaultFont(font)

        if is_dark_mode():
            self._apply_dark_editor_colours(editor)

        editor.setLexer(self.lexer)
        return editor

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
            self._set_editor_text(self.store.read(path))
            self._set_editor_modified(False)

            self.current_path = path
            self._dirty = False

            self._update_status("Loaded")
            self.script_changed.emit(path)
            self.script_browser.select_path(path)
        finally:
            self._loading = False

        return True

    def save(self):
        if self.current_path is None:
            self.load()

        self.store.write(
            self.current_path,
            self._editor_text(),
        )

        self._set_editor_modified(False)
        self._dirty = False
        self._update_status("Saved")

        return True

    def run(self):
        self.save()
        self.run_requested.emit(self._editor_text())
        self._update_status("Ran")

    def _set_editor_text(self, text):
        self.editor.setText(text)

    def _editor_text(self):
        return self.editor.text()

    def _set_editor_modified(self, modified):
        self.editor.setModified(bool(modified))

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
            self.status_label.setText(f"*{self.current_path.name}")
        else:
            self.status_label.clear()

        if action != "Modified":
            self.status_changed.emit(f"{action} {self.current_path.name}")

    def _set_script_browser_visible(self, visible):
        sizes = self.splitter.sizes()
        total = max(sum(sizes), 1)

        if visible:
            self.splitter.setSizes(
                [self._script_browser_width, max(total - self._script_browser_width, 1)]
            )
            return

        if sizes and sizes[0] > 0:
            self._script_browser_width = sizes[0]

        self.splitter.setSizes([0, total])
