import pytest
from pyqtgraph.Qt import QtWidgets

from attractors.console.script_panel import ScriptPanel


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    return app


def test_script_panel_restores_existing_script(qapp, tmp_path):
    scripts_dir = tmp_path / "scripts"
    script = scripts_dir / "new_script.py"
    scripts_dir.mkdir()
    script.write_text("print('Testing')\n", encoding="utf-8")

    panel = ScriptPanel(scripts_dir)

    assert panel.restore_script(script) is True
    assert panel.current_script_path() == script.resolve()
    assert panel._editor_text() == "print('Testing')\n"


def test_script_restore_to_scratch_when_missing(qapp, tmp_path):
    scripts_dir = tmp_path / "scripts"
    panel = ScriptPanel(scripts_dir)

    missing = scripts_dir / "missing.py"

    assert panel.restore_script(missing) is True
    assert panel.current_script_path() == (scripts_dir / "scratch.py").resolve()


def test_script_restore_rejects_outisde_path(qapp, tmp_path):
    scripts_dir = tmp_path / "scipts"
    outside = tmp_path / "outside.py"
    outside.write_text("print('Testing')", encoding="utf-8")

    panel = ScriptPanel(scripts_dir)

    assert panel.restore_script(outside) is True
    assert panel.current_script_path() == (scripts_dir / "scratch.py").resolve()


def test_script_panel_run_selection(qapp, tmp_path):
    panel = ScriptPanel(tmp_path / "scripts")
    emitted = []
    panel.run_requested.connect(emitted.append)

    panel.editor.setText("x = 1\ny = 2\nprint(x + y)\n")
    panel.editor.setSelection(1, 0, 1, 5)

    panel.run_selection()

    assert emitted == ["y = 2"]


def test_script_panel_run_selection_no_selection(qapp, tmp_path):
    panel = ScriptPanel(tmp_path / "scripts")
    emitted = []
    statuses = []
    panel.run_requested.connect(emitted.append)
    panel.status_changed.connect(statuses.append)

    panel.editor.setText("x = 1\n")
    panel.run_selection()

    assert emitted == []
    assert statuses[-1] == "No selection scratch.py"


def test_script_panel_run_saves_and_emits_full_script(qapp, tmp_path):
    scripts_dir = tmp_path / "scripts"
    script = scripts_dir / "test_script.py"
    scripts_dir.mkdir()
    script.write_text("old = 1\n", encoding="utf-8")

    panel = ScriptPanel(scripts_dir)
    panel.load_script(script)
    panel.editor.setText("new = 2\n")

    emitted = []
    panel.run_requested.connect(emitted.append)

    panel.run()

    assert emitted == ["new = 2\n"]
    assert script.read_text(encoding="utf-8") == "new = 2\n"
