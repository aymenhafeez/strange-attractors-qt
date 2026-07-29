from pyqtgraph.Qt import QtCore, QtWidgets


class PresetPanel(QtWidgets.QWidget):
    preset_save_requested = QtCore.pyqtSignal(str, str)
    preset_load_requested = QtCore.pyqtSignal(str)
    preset_delete_requested = QtCore.pyqtSignal(str)
    preset_selected = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.preset_label = QtWidgets.QLabel("Preset library")
        self.preset_name_edit = QtWidgets.QLineEdit()
        self.preset_name_edit.setPlaceholderText("Preset name")
        self.preset_notes_edit = QtWidgets.QTextEdit()
        self.preset_notes_edit.setPlaceholderText("Notes")
        self.preset_notes_edit.setFixedHeight(70)
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        self.preset_summary = QtWidgets.QLabel("No saved presets")
        self.preset_summary.setWordWrap(True)
        self.save_preset_button = QtWidgets.QPushButton("Save")
        self.save_preset_button.clicked.connect(self._emit_preset_save)
        self.load_preset_button = QtWidgets.QPushButton("Load")
        self.load_preset_button.clicked.connect(self._emit_preset_load)
        self.delete_preset_button = QtWidgets.QPushButton("Delete")
        self.delete_preset_button.clicked.connect(self._emit_preset_delete)

        layout.addWidget(self.preset_label, 0, 0, 1, 2)
        layout.addWidget(self.preset_combo, 1, 0, 1, 2)
        layout.addWidget(self.preset_name_edit, 2, 0, 1, 2)
        layout.addWidget(self.preset_notes_edit, 3, 0, 1, 2)
        layout.addWidget(self.preset_summary, 4, 0, 1, 2)
        layout.addWidget(self.save_preset_button, 5, 0)
        layout.addWidget(self.load_preset_button, 5, 1)
        layout.addWidget(self.delete_preset_button, 6, 0, 1, 2)
        layout.setRowStretch(7, 1)

    def set_saved_presets(self, names, selected=None):
        selected_name = selected or self.current_preset_name()
        with QtCore.QSignalBlocker(self.preset_combo):
            self.preset_combo.clear()
            self.preset_combo.addItems(names)
            if selected_name in names:
                self.preset_combo.setCurrentText(selected_name)

        has_presets = self.preset_combo.count() > 0
        self.load_preset_button.setEnabled(has_presets)
        self.delete_preset_button.setEnabled(has_presets)
        self._on_preset_selected(self.preset_combo.currentText())

    def current_preset_name(self):
        return self.preset_combo.currentText().strip()

    def set_preset_notes(self, notes):
        with QtCore.QSignalBlocker(self.preset_notes_edit):
            self.preset_notes_edit.setPlainText(notes)

    def set_preset_summary(self, summary):
        self.preset_summary.setText(summary or "No saved presets")

    def _preset_name_from_edit_or_combo(self):
        return self.preset_name_edit.text().strip() or self.current_preset_name()

    def _on_preset_selected(self, name):
        with QtCore.QSignalBlocker(self.preset_name_edit):
            self.preset_name_edit.setText(name)
        self.preset_selected.emit(name)

    def _emit_preset_save(self):
        self.preset_save_requested.emit(
            self._preset_name_from_edit_or_combo(),
            self.preset_notes_edit.toPlainText().strip(),
        )

    def _emit_preset_load(self):
        self.preset_load_requested.emit(self.current_preset_name())

    def _emit_preset_delete(self):
        self.preset_delete_requested.emit(self.current_preset_name())
