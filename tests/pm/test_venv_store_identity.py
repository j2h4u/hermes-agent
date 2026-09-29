"""A dependency generation follows the interpreter store it was built against."""

from pm.packages import Venv


def test_venv_stamp_changes_when_python_store_moves(tmp_path, monkeypatch):
    package = Venv()
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path / "first"))
    first = package.expected_stamp([], plugin_dirs=[])
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path / "second"))
    assert package.expected_stamp([], plugin_dirs=[]) != first
