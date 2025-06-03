# test_app.py

import sys
import subprocess
import importlib
import logging
import pytest
from types import ModuleType

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app as bootstrap


# --- Helpers to restore environment after each test ---
@pytest.fixture(autouse=True)
def restore_sys_modules(monkeypatch):
    """
    Restore sys.modules and sys.exit after each test.
    """
    saved_modules = sys.modules.copy()
    saved_exit = sys.exit
    yield
    sys.modules.clear()
    sys.modules.update(saved_modules)
    sys.exit = saved_exit


# --- Tests for Version Check ---
def test_version_too_low(monkeypatch, caplog):
    """
    If sys.version_info is lower than MIN_PYTHON, app should log a critical error and call sys.exit(1).
    """
    monkeypatch.setattr(sys, "version_info", (3, 6, 0))
    exited = []

    def fake_exit(code=0):
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    caplog.set_level(logging.INFO)
    with pytest.raises(SystemExit) as excinfo:
        importlib.reload(bootstrap)
    assert excinfo.value.code == 1
    assert exited == [1]
    assert "Python 3.7 or higher is required." in caplog.text


def test_version_ok(monkeypatch):
    """
    If sys.version_info meets MIN_PYTHON, no exit should occur on import.
    """
    monkeypatch.setattr(sys, "version_info", (3, 8, 0))
    module = importlib.reload(bootstrap)
    assert hasattr(module, "import_dependencies")


# --- Tests for install_requirements ---
def test_install_requirements_success(monkeypatch, caplog):
    """
    If subprocess.check_call succeeds, log messages should indicate installation succeeded.
    """
    called = []

    def fake_check_call(cmd):
        called.append(cmd)
        return 0

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)

    caplog.set_level(logging.INFO)
    bootstrap.install_requirements()
    assert called == [[sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]]
    assert "Installing required packages..." in caplog.text
    assert "Installation complete." in caplog.text


def test_install_requirements_failure(monkeypatch, caplog):
    """
    If subprocess.check_call raises CalledProcessError, install_requirements logs an error and exits.
    """
    def fake_check_call(cmd):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)

    exited = []

    def fake_exit(code=0):
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    caplog.set_level(logging.INFO)
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.install_requirements()
    assert excinfo.value.code == 1
    assert exited == [1]
    assert "Failed to install requirements." in caplog.text


# --- Tests for import_dependencies ---
def test_import_dependencies_already_present(monkeypatch):
    """
    If PyQt5 and QsciScintilla are already importable, import_dependencies should return QtWidgets.
    """
    dummy_pyqt5 = ModuleType("PyQt5")
    dummy_qsci = ModuleType("PyQt5.Qsci")
    dummy_qtwidgets = ModuleType("PyQt5.QtWidgets")

    # Make QsciScintilla available under PyQt5.Qsci
    dummy_qsci.QsciScintilla = object
    dummy_pyqt5.Qsci = dummy_qsci

    # Make QtWidgets available under PyQt5
    dummy_pyqt5.QtWidgets = dummy_qtwidgets

    monkeypatch.setitem(sys.modules, "PyQt5", dummy_pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.Qsci", dummy_qsci)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", dummy_qtwidgets)

    QtWidgets = bootstrap.import_dependencies()
    assert QtWidgets is dummy_qtwidgets


def test_import_dependencies_missing_then_installed(monkeypatch):
    """
    If PyQt5 is missing initially, install_requirements is called, then the imports succeed.
    """
    monkeypatch.setitem(sys.modules, "PyQt5", None)
    monkeypatch.setitem(sys.modules, "PyQt5.Qsci", None)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", None)

    installed = []

    def fake_install():
        installed.append(True)
        dummy_pyqt5 = ModuleType("PyQt5")
        dummy_qsci = ModuleType("PyQt5.Qsci")
        dummy_qtwidgets = ModuleType("PyQt5.QtWidgets")
        dummy_qsci.QsciScintilla = object
        dummy_pyqt5.Qsci = dummy_qsci
        dummy_pyqt5.QtWidgets = dummy_qtwidgets
        sys.modules["PyQt5"] = dummy_pyqt5
        sys.modules["PyQt5.Qsci"] = dummy_qsci
        sys.modules["PyQt5.QtWidgets"] = dummy_qtwidgets

    monkeypatch.setattr(bootstrap, "install_requirements", fake_install)

    QtWidgets = bootstrap.import_dependencies()
    assert installed == [True]
    assert QtWidgets is sys.modules["PyQt5.QtWidgets"]


def test_import_dependencies_still_missing(monkeypatch, caplog):
    """
    If PyQt5 remains missing after install_requirements, import_dependencies should exit.
    """
    monkeypatch.setitem(sys.modules, "PyQt5", None)
    monkeypatch.setitem(sys.modules, "PyQt5.Qsci", None)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", None)

    def fake_install():
        return

    monkeypatch.setattr(bootstrap, "install_requirements", fake_install)

    exited = []

    def fake_exit(code=0):
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.import_dependencies()
    assert excinfo.value.code == 1
    assert "PyQt5 or QScintilla still not found after installation." in caplog.text


# --- Tests for main() ---
def test_main_import_gui_failure(monkeypatch, caplog):
    """
    If importing SQLFormatterApp fails, main() logs an error and exits.
    """
    # Mock import_dependencies to succeed
    dummy_qtwidgets = ModuleType("PyQt5.QtWidgets")
    dummy_qtwidgets.QApplication = lambda *args, **kwargs: None
    monkeypatch.setattr(bootstrap, "import_dependencies", lambda: dummy_qtwidgets)

    # Ensure gui_app import fails
    monkeypatch.setitem(sys.modules, "gui_app", None)

    exited = []

    def fake_exit(code=0):
        exited.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as excinfo:
        bootstrap.main()
    assert excinfo.value.code == 1
    assert "Failed to import GUI application" in caplog.text


def test_main_success(monkeypatch):
    """
    If all imports succeed, main() should create a QApplication and SQLFormatterApp.
    We monkeypatch QApplication and SQLFormatterApp to avoid launching a real GUI.
    """
    class DummyApp:
        def __init__(self, args):
            pass

        def exec_(self):
            return 0

    class DummyWindow:
        def __init__(self):
            pass

        def show(self):
            pass

    # Mock import_dependencies to return Dummy QApplication
    dummy_qtwidgets = ModuleType("PyQt5.QtWidgets")
    dummy_qtwidgets.QApplication = DummyApp
    monkeypatch.setattr(bootstrap, "import_dependencies", lambda: dummy_qtwidgets)

    gui_app = ModuleType("gui_app")
    gui_app.SQLFormatterApp = DummyWindow
    monkeypatch.setitem(sys.modules, "gui_app", gui_app)

    exit_code_container = []

    def fake_exit(code=0):
        exit_code_container.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        bootstrap.main()
    assert excinfo.value.code == 0
    assert exit_code_container == [0]
