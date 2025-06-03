import sys
import os
import pytest
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.Qsci import QsciScintilla

# Ensure we can import gui_app.py from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import gui_app


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """
    Create a single QApplication for all tests.
    """
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    yield app


# --- Tests for DroppableQsciScintilla ---
class DummyEvent:
    def __init__(self, urls=None, text=None):
        self._mime = SimpleNamespace()
        if urls is not None:
            self._mime.hasUrls = lambda: True
            self._mime.urls = lambda: urls
        else:
            self._mime.hasUrls = lambda: False
            self._mime.urls = lambda: []
        if text is not None:
            self._mime.hasText = lambda: True
            self._mime.text = lambda: text
        else:
            self._mime.hasText = lambda: False
            self._mime.text = lambda: ""
        self._accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self._accepted = True

    def ignore(self):
        self._accepted = False


def test_is_droppable_urls_and_text():
    editor = gui_app.DroppableQsciScintilla()
    # Simulate event with URLs
    urls = [SimpleNamespace(toLocalFile=lambda: "/dummy.sql")]
    event_urls = DummyEvent(urls=urls)
    assert editor._is_droppable(event_urls) is True

    # Simulate event with text only
    event_text = DummyEvent(text="SELECT 1;")
    assert editor._is_droppable(event_text) is True

    # Simulate event with neither
    event_none = DummyEvent()
    assert editor._is_droppable(event_none) is False


def test_drag_enter_move_accepts_or_passes(monkeypatch):
    editor = gui_app.DroppableQsciScintilla()

    # When droppable, acceptProposedAction is called
    urls = [SimpleNamespace(toLocalFile=lambda: "/file.sql")]
    event = DummyEvent(urls=urls)
    editor.dragEnterEvent(event)
    assert event._accepted is True

    event2 = DummyEvent(text="abc")
    editor.dragMoveEvent(event2)
    assert event2._accepted is True

    # When not droppable, QsciScintilla methods are called
    called = {"enter": False, "move": False}

    class Parent:
        def dragEnterEvent(self, e):
            called["enter"] = True

        def dragMoveEvent(self, e):
            called["move"] = True

    monkeypatch.setattr(gui_app.QsciScintilla, "dragEnterEvent", Parent.dragEnterEvent)
    monkeypatch.setattr(gui_app.QsciScintilla, "dragMoveEvent", Parent.dragMoveEvent)

    event3 = DummyEvent()
    editor.dragEnterEvent(event3)
    assert called["enter"] is True

    event4 = DummyEvent()
    editor.dragMoveEvent(event4)
    assert called["move"] is True


def test_drop_event_with_valid_file(tmp_path):
    # Create a temporary .sql file
    file_path = tmp_path / "test.sql"
    file_path.write_text("SELECT 1;")

    dummy_url = SimpleNamespace(toLocalFile=lambda: str(file_path))
    event = DummyEvent(urls=[dummy_url])

    class ParentApp:
        def __init__(self):
            self.called = False

        def format_sql_from_input(self):
            self.called = True

    parent = ParentApp()
    editor = gui_app.DroppableQsciScintilla(parent_app=parent)

    # Before drop, editor is empty
    assert editor.text() == ""

    editor.dropEvent(event)
    # After drop, editor text matches file content
    assert editor.text() == "SELECT 1;"
    # Parent's format_sql_from_input should have been called
    assert parent.called is True
    # Event accepted
    assert event._accepted is True


def test_drop_event_with_non_sql_file(tmp_path, capsys):
    file_path = tmp_path / "image.png"
    file_path.write_text("not sql")

    dummy_url = SimpleNamespace(toLocalFile=lambda: str(file_path))
    event = DummyEvent(urls=[dummy_url])

    editor = gui_app.DroppableQsciScintilla()
    editor.dropEvent(event)
    captured = capsys.readouterr()
    assert "Ignored non-SQL/TXT file" in captured.out
    assert event._accepted is False


def test_drop_event_with_text_only():
    event = DummyEvent(text="INSERT INTO tbl VALUES (1);")
    editor = gui_app.DroppableQsciScintilla()
    editor.setText("")

    editor.dropEvent(event)
    assert editor.text() == "INSERT INTO tbl VALUES (1);"
    assert event._accepted is True


# --- Tests for SQLFormatterApp ---
def test_format_sql_from_input(tmp_path, monkeypatch):
    app = gui_app.SQLFormatterApp()
    cache_file = tmp_path / "last_input.sql"
    app.cache_file = str(cache_file)

    def fake_format_all(sql_text, pretty_json=True):
        return "FORMATTED:" + sql_text

    monkeypatch.setattr(gui_app.SQLFormatter.SQLFormatter, "format_all", fake_format_all)

    app.input_text.setText("SELECT 2;")
    app.json_checkbox.setChecked(False)

    app.format_sql_from_input()

    assert app.output_text.text() == "FORMATTED:SELECT 2;"
    assert cache_file.read_text() == "SELECT 2;"


from PyQt5.Qsci import QsciScintilla

def test_toggle_theme_changes_editor_background():
    app = gui_app.SQLFormatterApp()

    # Dark mode toggle
    app.dark_mode_checkbox.setChecked(True)
    app.toggle_theme()
    QApplication.processEvents()
    dark_bg = app.input_lexer.paper(QsciScintilla.STYLE_DEFAULT).name()
    assert dark_bg == gui_app.COLOR_DARK_BG.name(), f"Expected dark bg {gui_app.COLOR_DARK_BG.name()} but got {dark_bg}"

    # Light mode toggle
    app.dark_mode_checkbox.setChecked(False)
    app.toggle_theme()
    QApplication.processEvents()
    light_bg = app.input_lexer.paper(QsciScintilla.STYLE_DEFAULT).name()
    assert light_bg == gui_app.COLOR_LIGHT_BG.name(), f"Expected light bg {gui_app.COLOR_LIGHT_BG.name()} but got {light_bg}"

    # Final check that the values differ
    assert dark_bg != light_bg, f"Expected dark and light backgrounds to differ, got {dark_bg} both times"


def test_load_cached_input(tmp_path):
    cache_file = tmp_path / "last_input.sql"
    cache_file.write_text("TEST_INLINE;")

    app = gui_app.SQLFormatterApp()
    app.cache_file = str(cache_file)
    app.input_text.setText("")
    app._load_cached_input()
    assert app.input_text.text() == "TEST_INLINE;"


def test_event_filter_ctrl_enter(monkeypatch):
    app = gui_app.SQLFormatterApp()
    called = []

    def fake_format():
        called.append(True)

    monkeypatch.setattr(app, "format_sql_from_input", fake_format)

    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.ControlModifier)
    handled = app.eventFilter(None, event)
    assert handled is True
    assert called == [True]


def test_copy_output_to_clipboard(monkeypatch):
    app = gui_app.SQLFormatterApp()
    app.output_text.setText("COPY_ME;")

    class FakeClipboard:
        def __init__(self):
            self.data = ""

        def setText(self, text):
            self.data = text

    fake_clip = FakeClipboard()
    monkeypatch.setattr(QApplication, "clipboard", lambda: fake_clip)

    app.copy_output()
    assert fake_clip.data == "COPY_ME;"
