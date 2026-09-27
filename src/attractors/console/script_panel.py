from pathlib import Path

from PyQt6.Qsci import QsciLexerPython, QsciScintilla
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from ..ui.style import SPLITTER_HANDLE_HOVER, is_dark_mode, SCRIPT_PANEL
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

def dark_mode():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False

    scheme = app.styleHints().colorScheme()
    if scheme != QtCore.Qt.ColorScheme.Unknown:
        return scheme == QtCore.Qt.ColorScheme.Dark

    palette = app.palette()
    window = palette.color(QtGui.QPalette.ColorRole.Window)
    text = palette.color(QtGui.QPalette.ColorRole.WindowText)

    return window.lightness() < text.lightness()


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
        self.setObjectName("scriptPanel")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(SCRIPT_PANEL)
        self.store = ScriptStore(scripts_dir)
        self.scripts_dir = self.store.root
        self.script_path = self.scripts_dir / "scratch.py"
        # self.current_path = None
        # self._loading = False
        # self._dirty = False
        self._paths = {}
        self._script_browser_width = 220

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.script_browser = ScriptBrowser(self.scripts_dir)
        self.script_browser.confirm_delete = self._confirm_delete
        self.script_browser.script_selected.connect(self.load_script)
        self.script_browser.path_renamed.connect(self._on_path_renamed)
        self.script_browser.path_deleted.connect(self._on_path_deleted)

        editor_host = QtWidgets.QWidget()
        editor_layout = QtWidgets.QVBoxLayout(editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

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

        self.run_selection_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("system-run"), "Run selection"
        )
        self.run_selection_action.setToolTip("Run selection")

        self.save_action = self.toolbar.addAction(
            QtGui.QIcon.fromTheme("document-save"), "Save"
        )
        self.save_action.setToolTip("Save script")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        editor_layout.addWidget(self.toolbar)
        editor_layout.addWidget(self.tabs, 1)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.script_browser)
        self.splitter.addWidget(editor_host)
        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([200, 620])
        # self.splitter.setContentsMargins(0, 0, 0, 0)
        self.splitter.setStyleSheet(SPLITTER_HANDLE_HOVER)
        layout.addWidget(self.splitter)

        self.run_action.triggered.connect(self.run)
        self.run_selection_action.triggered.connect(self.run_selection)
        self.save_action.triggered.connect(self.save)

        self.load()

    @property
    def editor(self):
        return self.tabs.currentWidget()

    def _path_for(self, editor):
        return self._paths.get(editor)

    def _editor_for(self, path):
        return next(
            (
                editor
                for editor, editor_path in self._paths.items()
                if editor_path == path
            ),
            None,
        )

    def _ensure_scratch(self):
        if not self.script_path.exists():
            self.store.write(self.script_path, "")

    def _remove_editor(self, editor):
        self._paths.pop(editor)
        self.tabs.removeTab(self.tabs.indexOf(editor))
        editor.deleteLater()

    def _update_tab_title(self, editor):
        index = self.tabs.indexOf(editor)
        if index < 0:
            return

        path = self._path_for(editor)
        prefix = "*" if editor.isModified() else ""
        self.tabs.setTabText(index, f"{prefix}{path.name}")
        self.tabs.setTabToolTip(index, str(path))

    def example_scripts(self):
        examples_dir = self.scripts_dir / "examples"
        if not examples_dir.exists():
            return []

        return sorted(examples_dir.glob("*.py"), key=lambda p: p.name.lower())

    def _on_path_renamed(self, old_path, new_path):
        old_path = Path(old_path).resolve()
        new_path = Path(new_path).resolve()
        active_editor = self.editor
        active_path_changed = False

        for editor, path in list(self._paths.items()):
            if path == old_path:
                renamed_path = new_path
            elif old_path in path.parents:
                renamed_path = new_path / path.relative_to(old_path)
            else:
                continue

            self._paths[editor] = renamed_path
            self._update_tab_title(editor)

            if editor is active_editor:
                active_path_changed = True

        if active_path_changed:
            current_path = self.current_script_path()
            self._update_status("Renamed")
            self.script_changed.emit(current_path)
            self.script_browser.select_path(current_path)

    def _on_path_deleted(self, path):
        for editor, editor_path in list(self._paths.items()):
            if self._check_match(path, editor_path):
                self._remove_editor(editor)

        if self.tabs.count() == 0:
            self._ensure_scratch()
            self.load_script(self.script_path)

    def _check_match(self, parent, child):
        parent = Path(parent).resolve()
        child = Path(child).resolve()

        return child == parent or parent in child.parents

    def _apply_dark_editor_colours(self, editor, lexer):
        editor.setCaretForegroundColor(QtGui.QColor(EDITOR_TEXT))
        editor.setCaretLineBackgroundColor(QtGui.QColor(EDITOR_CARET_LINE))
        editor.setColor(QtGui.QColor(EDITOR_TEXT))
        editor.setPaper(QtGui.QColor(EDITOR_BACKGROUND))
        editor.setSelectionBackgroundColor(QtGui.QColor(EDITOR_SELECTION))
        editor.setSelectionForegroundColor(QtGui.QColor(EDITOR_TEXT))
        editor.setMarginsBackgroundColor(QtGui.QColor(EDITOR_MARGIN))
        editor.setMarginsForegroundColor(QtGui.QColor(EDITOR_MARGIN_TEXT))
        lexer.setDefaultColor(QtGui.QColor(EDITOR_TEXT))
        lexer.setDefaultPaper(QtGui.QColor(EDITOR_BACKGROUND))

        for style, colour in PYTHON_STYLE_COLOURS.items():
            lexer.setColor(QtGui.QColor(colour), style)
            lexer.setPaper(QtGui.QColor(EDITOR_BACKGROUND), style)

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

        lexer = QsciLexerPython(editor)
        lexer.setDefaultFont(font)

        if dark_mode():
            self._apply_dark_editor_colours(editor, lexer)

        editor.setLexer(lexer)

        return editor

    def load(self):
        self.store.ensure_root()
        self._ensure_scratch()
        self.load_script(self.script_path)

    def load_script(self, path):
        path = self.store.resolve_script(path)

        existing = self._editor_for(path)
        if existing is not None:
            self.tabs.setCurrentWidget(existing)
            return True

        text = self.store.read(path)
        editor = self._build_editor()
        editor.setText(text)
        editor.setModified(False)

        self._paths[editor] = path
        editor.textChanged.connect(
            lambda editor=editor: self._on_editor_text_changed(editor)
        )

        index = self.tabs.addTab(editor, path.name)
        self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)
        self._update_status("Loaded")
        return True

    def _on_tab_changed(self, _index):
        path = self.current_script_path()
        self._update_status("")

        if path is not None:
            self.script_changed.emit(path)
            self.script_browser.select_path(path)

    def current_script_path(self):
        return self._path_for(self.editor)

    def open_script_paths(self):
        return [
            self._path_for(self.tabs.widget(index))
            for index in range(self.tabs.count())
        ]

    def restore_script(self, path):
        if path is None:
            return self.load_script(self.script_path)

        try:
            path = self.store.resolve_script(path)
        except ValueError:
            return self.load_script(self.script_path)

        if not path.exists():
            return self.load_script(self.script_path)

        return self.load_script(path)

    def restore_scripts(self, paths, active_path):
        for editor in list(self._paths):
            self._remove_editor(editor)

        for raw_path in paths:
            try:
                path = self.store.resolve_script(raw_path)
            except (TypeError, ValueError):
                continue

            if path.exists():
                self.load_script(path)

        if active_path is not None:
            self.restore_script(active_path)

        if self.tabs.count() == 0:
            self._ensure_scratch()
            self.load_script(self.script_path)

    def _save_editor(self, editor):
        path = self._path_for(editor)
        self.store.write(path, editor.text())
        editor.setModified(False)
        self._update_tab_title(editor)

        if editor is self.editor:
            self._update_status("Saved")

        return True

    def save(self):
        if self.editor is None:
            return False

        return self._save_editor(self.editor)

    def run(self):
        if not self.save():
            return

        self.run_requested.emit(self.editor.text())
        self._update_status("Ran")

    def run_selection(self):
        if self.editor is None:
            return

        text = self.editor.selectedText()
        if not text:
            self._update_status("No selection")
            return

        self.run_requested.emit(text)
        self._update_status("Ran selection")

    def _set_editor_text(self, text):
        self.editor.setText(text)

    def _editor_text(self):
        return self.editor.text()

    def _set_editor_modified(self, modified):
        self.editor.setModified(bool(modified))
        self._update_tab_title(self.editor)

    def _on_editor_text_changed(self, editor):
        self._update_tab_title(editor)
        if editor is self.editor:
            self._update_status("Modified")

    def _confirm_dirty_editors(self, editors, message):
        dirty = [editor for editor in editors if editor.isModified()]
        if not dirty:
            return True

        result = QtWidgets.QMessageBox.question(
            self,
            "Unsaved scripts",
            message,
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )

        if result == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False

        if result == QtWidgets.QMessageBox.StandardButton.Save:
            for editor in dirty:
                self._save_editor(editor)

            return True

        return result == QtWidgets.QMessageBox.StandardButton.Discard

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if editor is None:
            return

        path = self._path_for(editor)
        if not self._confirm_dirty_editors(
            [editor],
            f"Save changes to '{path.name}' before closing it?",
        ):
            return

        self._remove_editor(editor)

        if self.tabs.count() == 0:
            self._ensure_scratch()
            self.load_script(self.script_path)

    def _confirm_delete(self, path):
        affected = [
            editor
            for editor, editor_path in self._paths.items()
            if self._check_match(path, editor_path)
        ]
        return self._confirm_dirty_editors(
            affected,
            "Save changes to open scripts before deleting?",
        )

    def confirm_close(self):
        return self._confirm_dirty_editors(
            list(self._paths),
            "Save changes to open scripts before exiting?",
        )

    def _update_status(self, action):
        path = self.current_script_path()
        if path is None:
            self.status_label.clear()
            self.status_changed.emit("")
            return

        self.status_label.setText(f"*{path.name}" if self.editor.isModified() else "")

        if action and action != "Modified":
            self.status_changed.emit(f"{action} {path.name}")

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
