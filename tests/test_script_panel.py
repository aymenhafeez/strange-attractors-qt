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
