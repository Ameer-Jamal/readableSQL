from PyQt5.Qsci import QsciScintilla, QsciLexerSQL
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy,
    QSplitter, QCheckBox, QDesktopWidget
)

import SQLFormatter

# Named constants for fonts and colors
FONT_MONO = QFont("Courier New", 14)
FONT_SIG = QFont("Courier New", 11, italic=True)

# Light theme colors
COLOR_LIGHT_BG = QColor("#f0f0f0")
COLOR_LIGHT_FG = QColor("#000000")
COLOR_MARGINS_BG = QColor("#e0e0e0")
COLOR_MARGINS_FG = QColor("#505050")
COLOR_SELECTION_BG = QColor("#add8e6")

# Dark theme colors
COLOR_DARK_BG = QColor("#1e1e1e")
COLOR_DARK_FG = QColor("#dcdcdc")
COLOR_DARK_MARGINS_BG = QColor("#2b2b2b")
COLOR_DARK_MARGINS_FG = QColor("#858585")
COLOR_DARK_SELECTION_BG = QColor("#264F78")
COLOR_DARK_SELECTION_FG = QColor("#FFFFFF")

# Lexer token color maps
LIGHT_LEXER_COLORS = {
    QsciLexerSQL.Keyword: QColor("blue"),
    QsciLexerSQL.Comment: QColor("green"),
    QsciLexerSQL.CommentLine: QColor("green"),
    QsciLexerSQL.Number: QColor("magenta"),
    QsciLexerSQL.SingleQuotedString: QColor(160, 32, 32),
    QsciLexerSQL.DoubleQuotedString: QColor(160, 32, 32),
    QsciLexerSQL.Identifier: COLOR_LIGHT_FG,
    QsciLexerSQL.Operator: COLOR_LIGHT_FG,
    QsciLexerSQL.Default: COLOR_LIGHT_FG,
}

DARK_LEXER_COLORS = {
    QsciLexerSQL.Keyword: QColor("#569cd6"),
    QsciLexerSQL.Number: QColor("#b5cea8"),
    QsciLexerSQL.Comment: QColor("#6A9955"),
    QsciLexerSQL.CommentLine: QColor("#6A9955"),
    QsciLexerSQL.DoubleQuotedString: QColor("#ce9178"),
    QsciLexerSQL.SingleQuotedString: QColor("#ce9178"),
    QsciLexerSQL.Operator: QColor("#d4d4d4"),
    QsciLexerSQL.Identifier: QColor("#9cdcfe"),
    QsciLexerSQL.QuotedIdentifier: QColor("#d7ba7d"),
    QsciLexerSQL.Default: COLOR_DARK_FG,
}


class DroppableQsciScintilla(QsciScintilla):
    def __init__(self, parent_app=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_app = parent_app
        self.setAcceptDrops(True)

    def _is_droppable(self, event) -> bool:
        """Return True if the drag event contains URLs or plain text."""
        mime_data = event.mimeData()
        return mime_data.hasUrls() or mime_data.hasText()

    def dragEnterEvent(self, event):
        if self._is_droppable(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._is_droppable(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path:
                    try:
                        if file_path.lower().endswith(('.sql', '.txt')):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            self.setText(content)
                            event.acceptProposedAction()
                            if self.parent_app and hasattr(self.parent_app, 'format_sql_from_input'):
                                self.parent_app.format_sql_from_input()
                            return
                        else:
                            print(f"Ignored non-SQL/TXT file: {file_path}")
                            event.ignore()
                    except Exception as e:
                        print(f"Error reading dropped file {file_path}: {e}")
                        if self.parent_app and hasattr(self.parent_app, 'show_user_error'):
                            self.parent_app.show_user_error(f"Could not load file: {e}")
                        event.ignore()
                else:
                    super().dropEvent(event)
            else:
                super().dropEvent(event)
        elif mime_data.hasText():
            self.insert(mime_data.text())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class SQLFormatterApp(QWidget):
    """
    A PyQt5-based GUI application that allows dragging in SQL/TXT files or pasting raw SQL,
    formats them with SQLFormatter.SQLFormatter, and displays the result in a QsciScintilla editor.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL Formatter")
        screen_geo = QDesktopWidget().screenGeometry()
        initial_width = int(screen_geo.width() * 0.8)
        initial_height = int(screen_geo.height() * 0.9)
        self.resize(initial_width, initial_height)

        FONT_MONO.setStyleHint(QFont.Monospace)
        self.mono = FONT_MONO
        self.cache_file = "last_input.sql"
        self.input_lexer = None
        self.output_lexer = None
        self.settings = QSettings("AmeerJ", "SQLFormatterApp")

        self._setup_ui()
        self._load_cached_input()
        if self.input_text.text().strip():
            self.format_sql_from_input()

        self.installEventFilter(self)
        geometry = self.settings.value("windowGeometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _configure_editor(self, editor: QsciScintilla, with_lexer: bool) -> QsciLexerSQL:
        """
        Common Scintilla editor setup: font, margins, utf8, and optional SQL lexer.
        Returns the created lexer or None.
        """
        editor.setFont(self.mono)
        editor.setUtf8(True)
        editor.setReadOnly(False)
        editor.setMarginsFont(self.mono)
        editor.setMarginType(0, QsciScintilla.NumberMargin)
        editor.setMarginWidth(0, "0000")
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if with_lexer:
            lexer = QsciLexerSQL()
            lexer.setDefaultFont(self.mono)
            editor.setLexer(lexer)
            return lexer
        return None

    def _create_scintilla_editor(self, with_lexer=True, read_only=False, make_droppable=False):
        editor = DroppableQsciScintilla(parent_app=self) if make_droppable else QsciScintilla()
        editor.setReadOnly(read_only)
        lexer = self._configure_editor(editor, with_lexer)
        return editor, lexer

    def _apply_lexer_theme(self, lexer, paper_color: QColor, default_fg: QColor, token_color_map: dict):
        """
        Apply theme to a given QsciLexerSQL: set default font, paper, and color per style number.
        """
        if not lexer:
            return
        lexer.setDefaultFont(self.mono)
        lexer.setDefaultPaper(paper_color)
        lexer.setDefaultColor(default_fg)
        for style_num in range(128):
            lexer.setFont(self.mono, style_num)
            lexer.setPaper(paper_color, style_num)
            fg_color = token_color_map.get(style_num, default_fg)
            lexer.setColor(fg_color, style_num)

    def _apply_editor_theme(self, editor, background: QColor, foreground: QColor,
                            margins_bg: QColor, margins_fg: QColor,
                            selection_bg: QColor, selection_fg: QColor):
        """
        Apply a theme (light or dark) to a QsciScintilla editor instance.
        """
        pal = editor.palette()
        pal.setColor(QPalette.Base, background)
        pal.setColor(QPalette.Text, foreground)
        editor.setPalette(pal)
        editor.setPaper(background)
        editor.setColor(foreground)
        editor.setCaretForegroundColor(foreground)
        editor.setMarginsBackgroundColor(margins_bg)
        editor.setMarginsForegroundColor(margins_fg)
        editor.setSelectionBackgroundColor(selection_bg)
        editor.setSelectionForegroundColor(selection_fg)

    def _save_splitter_state(self):
        """Save the current state of the splitter to settings."""
        self.settings.setValue("splitterState", self.splitter.saveState())

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(
            "Paste raw SQL statement or Drag and Drop a .sql/.txt file onto the input area:"))
        top_controls_layout = QHBoxLayout()

        self.json_checkbox = QCheckBox("Pretty JSON")
        self.json_checkbox.setFont(self.mono)
        self.json_checkbox.setChecked(self.settings.value("prettyJson", True, type=bool))
        self.json_checkbox.stateChanged.connect(self.save_checkbox_states)
        top_controls_layout.addWidget(self.json_checkbox)
        top_controls_layout.addStretch()

        self.dark_mode_checkbox = QCheckBox("Dark Mode")
        self.dark_mode_checkbox.setFont(self.mono)
        self.dark_mode_checkbox.setChecked(self.settings.value("darkMode", False, type=bool))
        self.dark_mode_checkbox.stateChanged.connect(self.toggle_theme)
        top_controls_layout.addWidget(self.dark_mode_checkbox)
        layout.addLayout(top_controls_layout)

        self.input_text, self.input_lexer = self._create_scintilla_editor(
            with_lexer=True,
            read_only=False,
            make_droppable=True
        )

        self.output_text, self.output_lexer = self._create_scintilla_editor(
            with_lexer=True,
            read_only=False,
            make_droppable=False
        )

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.input_text)
        self.splitter.addWidget(self.output_text)
        initial_window_height = self.height() if self.height() > 100 else 600
        self.splitter.setSizes([initial_window_height // 2, initial_window_height // 2])
        layout.addWidget(self.splitter)

        # Save/restore splitter state
        self.splitter.splitterMoved.connect(self._save_splitter_state)
        saved_state = self.settings.value("splitterState")
        if saved_state:
            self.splitter.restoreState(saved_state)

        btn_layout = QHBoxLayout()
        self.format_button = QPushButton("Format")
        self.format_button.setFont(self.mono)
        self.format_button.clicked.connect(self.format_sql_from_input)
        self.copy_button = QPushButton("Copy Output")
        self.copy_button.setFont(self.mono)
        self.copy_button.clicked.connect(self.copy_output)
        btn_layout.addWidget(self.format_button)
        btn_layout.addWidget(self.copy_button)
        layout.addLayout(btn_layout)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)  # Keep it hidden as errors are in output
        layout.addWidget(self.error_label)

        sig = QLabel("© 2025 Ameer Jamal")
        sig.setFont(FONT_SIG)
        sig.setStyleSheet("color: gray;")
        sig.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(sig)

        self.setLayout(layout)
        self.toggle_theme()

    def _load_cached_input(self):
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.input_text.setText(f.read())
        except FileNotFoundError:
            return
        except Exception as e:
            print(f"Error loading cached input: {e}")

    def toggle_theme(self):
        is_dark = self.dark_mode_checkbox.isChecked()
        self.settings.setValue("darkMode", is_dark)
        for editor, lexer in [(self.input_text, self.input_lexer),
                              (self.output_text, self.output_lexer)]:
            if not editor:
                continue
            if is_dark:
                self._apply_editor_theme(
                    editor,
                    background=COLOR_DARK_BG,
                    foreground=COLOR_DARK_FG,
                    margins_bg=COLOR_DARK_MARGINS_BG,
                    margins_fg=COLOR_DARK_MARGINS_FG,
                    selection_bg=COLOR_DARK_SELECTION_BG,
                    selection_fg=COLOR_DARK_SELECTION_FG,
                )
                self._apply_lexer_theme(
                    lexer,
                    paper_color=COLOR_DARK_BG,
                    default_fg=COLOR_DARK_FG,
                    token_color_map=DARK_LEXER_COLORS,
                )
            else:
                self._apply_editor_theme(
                    editor,
                    background=COLOR_LIGHT_BG,
                    foreground=COLOR_LIGHT_FG,
                    margins_bg=COLOR_MARGINS_BG,
                    margins_fg=COLOR_MARGINS_FG,
                    selection_bg=COLOR_SELECTION_BG,
                    selection_fg=COLOR_LIGHT_FG,
                )
                self._apply_lexer_theme(
                    lexer,
                    paper_color=COLOR_LIGHT_BG,
                    default_fg=COLOR_LIGHT_FG,
                    token_color_map=LIGHT_LEXER_COLORS,
                )
            editor.recolor()

    def save_checkbox_states(self):
        self.settings.setValue("prettyJson", self.json_checkbox.isChecked())

    def format_sql_from_input(self):
        sql = self.input_text.text()
        if sql.strip():
            with open(self.cache_file, "w", encoding="utf-8") as f:
                f.write(sql)

        pretty = self.json_checkbox.isChecked()
        try:
            formatted_output = SQLFormatter.SQLFormatter.format_all(sql, pretty_json=pretty)
        except Exception as e:
            formatted_output = f"❌ Critical error during formatting: {str(e)}\n\nPlease check the input SQL or report this bug."
            import traceback
            print(f"CRITICAL FORMATTING ERROR: {traceback.format_exc()}")

        self.output_text.setText(formatted_output)
        self.error_label.setText("")

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress and event.key() == Qt.Key_Return:
            if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
                self.format_sql_from_input()
                return True
        return super().eventFilter(obj, event)

    def copy_output(self):
        QApplication.clipboard().setText(self.output_text.text())

    def closeEvent(self, event):
        self.settings.setValue("windowGeometry", self.saveGeometry())
        super().closeEvent(event)

    def show_user_error(self, message):
        print(f"USER_ERROR: {message}")
