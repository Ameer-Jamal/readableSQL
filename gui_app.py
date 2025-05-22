from PyQt5.Qsci import QsciScintilla, QsciLexerSQL
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy, QSplitter, QCheckBox
)

import SQLFormatter


class SQLFormatterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL Formatter")
        self.setMinimumSize(900, 700)
        self.mono = QFont("Courier New", 14)
        self.mono.setStyleHint(QFont.Monospace)
        self.cache_file = "last_input.sql"

        self.input_lexer = None
        self.output_lexer = None

        self.settings = QSettings("SQLFormatterApp", "SQLFormatterApp")

        self._setup_ui()
        self._load_cached_input()
        self.installEventFilter(self)

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Paste raw SQL INSERT statement:"))

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

        self.input_text, self.input_lexer = self._create_scintilla_editor(with_lexer=True, read_only=False)
        self.output_text, self.output_lexer = self._create_scintilla_editor(with_lexer=True, read_only=True)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.input_text)
        splitter.addWidget(self.output_text)
        splitter.setSizes([self.height() // 2, self.height() // 2])
        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        self.format_button = QPushButton("Format")
        self.format_button.setFont(self.mono)
        self.format_button.clicked.connect(self.format_sql)
        self.copy_button = QPushButton("Copy Output")
        self.copy_button.setFont(self.mono)
        self.copy_button.clicked.connect(self.copy_output)
        btn_layout.addWidget(self.format_button)
        btn_layout.addWidget(self.copy_button)
        layout.addLayout(btn_layout)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)
        self.setLayout(layout)
        self.toggle_theme()

    def _load_cached_input(self):
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.input_text.setText(f.read())
        except FileNotFoundError:
            pass

    def _create_scintilla_editor(self, with_lexer=True, read_only=False):
        editor = QsciScintilla()
        editor.setFont(self.mono)
        editor.setUtf8(True)
        editor.setReadOnly(read_only)
        editor.setMarginsFont(self.mono)
        editor.setMarginType(0, QsciScintilla.NumberMargin)
        editor.setMarginWidth(0, "0000")
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        created_lexer = None
        if with_lexer:
            created_lexer = QsciLexerSQL()
            created_lexer.setDefaultFont(self.mono)
            editor.setLexer(created_lexer)
        return editor, created_lexer

    def _apply_original_light_lexer_styles(self, lexer):
        if not lexer: return
        light_paper_color = QColor("#f0f0f0")
        default_light_fg = QColor("#000000")
        lexer.setDefaultFont(self.mono)
        lexer.setDefaultPaper(light_paper_color)
        lexer.setDefaultColor(default_light_fg)
        for style_num in range(128):
            lexer.setFont(self.mono, style_num)
            lexer.setPaper(light_paper_color, style_num)
            current_fg = default_light_fg
            if style_num == QsciLexerSQL.Keyword:
                current_fg = QColor("blue")
            elif style_num == QsciLexerSQL.Comment or style_num == QsciLexerSQL.CommentLine:
                current_fg = QColor("green")
            elif style_num == QsciLexerSQL.Number:
                current_fg = QColor("magenta")
            elif style_num == QsciLexerSQL.SingleQuotedString or style_num == QsciLexerSQL.DoubleQuotedString:
                current_fg = QColor(160, 32, 32)
            lexer.setColor(current_fg, style_num)

    def _apply_editor_theme_light(self, editor):
        light_bg = QColor("#f0f0f0")
        light_fg = QColor("#000000")
        pal = editor.palette()
        pal.setColor(QPalette.Base, light_bg)
        pal.setColor(QPalette.Text, light_fg)
        editor.setPalette(pal)
        editor.setPaper(light_bg)
        editor.setColor(light_fg)
        editor.setCaretForegroundColor(light_fg)
        editor.setMarginsBackgroundColor(QColor("#e0e0e0"))
        editor.setMarginsForegroundColor(QColor("#505050"))
        editor.setSelectionBackgroundColor(QColor("#add8e6"))
        editor.setSelectionForegroundColor(light_fg)

    def _apply_editor_theme_dark(self, editor):
        dark_bg = QColor("#1e1e1e")
        dark_fg = QColor("#dcdcdc")
        pal = editor.palette()
        pal.setColor(QPalette.Base, dark_bg)
        pal.setColor(QPalette.Text, dark_fg)
        editor.setPalette(pal)
        editor.setPaper(dark_bg)
        editor.setColor(dark_fg)
        editor.setCaretForegroundColor(dark_fg)
        editor.setMarginsBackgroundColor(QColor("#2b2b2b"))
        editor.setMarginsForegroundColor(QColor("#858585"))
        editor.setSelectionBackgroundColor(QColor("#264F78"))
        editor.setSelectionForegroundColor(QColor("#FFFFFF"))

    def _apply_dark_lexer_styles(self, lexer):
        if not lexer: return
        dark_paper_color = QColor("#1e1e1e")
        default_dark_fg_color = QColor("#dcdcdc")
        lexer.setDefaultFont(self.mono)
        lexer.setDefaultPaper(dark_paper_color)
        lexer.setDefaultColor(default_dark_fg_color)
        dark_token_fg_colors = {
            QsciLexerSQL.Keyword: QColor("#569cd6"), QsciLexerSQL.Number: QColor("#b5cea8"),
            QsciLexerSQL.Comment: QColor("#6A9955"), QsciLexerSQL.CommentLine: QColor("#6A9955"),
            QsciLexerSQL.DoubleQuotedString: QColor("#ce9178"), QsciLexerSQL.SingleQuotedString: QColor("#ce9178"),
            QsciLexerSQL.Operator: QColor("#d4d4d4"), QsciLexerSQL.Identifier: QColor("#9cdcfe"),
            QsciLexerSQL.QuotedIdentifier: QColor("#d7ba7d"),
        }
        for style_num in range(128):
            lexer.setFont(self.mono, style_num)
            lexer.setPaper(dark_paper_color, style_num)
            fg_color = dark_token_fg_colors.get(style_num, default_dark_fg_color)
            lexer.setColor(fg_color, style_num)

    def toggle_theme(self):  # Also handles saving dark mode state
        is_dark = self.dark_mode_checkbox.isChecked()

        # <<< NEW: Save Dark Mode setting whenever it's toggled (or initially applied) >>>
        self.settings.setValue("darkMode", is_dark)

        editors_and_their_lexers = [
            (self.input_text, self.input_lexer),
            (self.output_text, self.output_lexer)
        ]
        for editor, current_lexer in editors_and_their_lexers:
            if not editor: continue
            if is_dark:
                self._apply_editor_theme_dark(editor)
                if current_lexer: self._apply_dark_lexer_styles(current_lexer)
            else:
                self._apply_editor_theme_light(editor)
                if current_lexer: self._apply_original_light_lexer_styles(current_lexer)
            editor.recolor()

    def save_checkbox_states(self):
        self.settings.setValue("prettyJson", self.json_checkbox.isChecked())

    def format_sql(self):
        sql = self.input_text.text()
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write(sql)
        pretty = self.json_checkbox.isChecked()

        if hasattr(SQLFormatter, 'SQLFormatter') and hasattr(SQLFormatter.SQLFormatter, 'format_all'):
            try:
                formatted_output = SQLFormatter.SQLFormatter.format_all(sql, pretty_json=pretty)
            except Exception as e:
                formatted_output = f"❌ Critical error during formatting: {str(e)}\n\nPlease check the input SQL or report this bug."
                import traceback
                print(f"CRITICAL FORMATTING ERROR: {traceback.format_exc()}")
        else:
            formatted_output = "❌ SQLFormatter module not configured correctly."

        self.output_text.setText(formatted_output)  # Always set the output_text
        # Clear it always, as errors are in the output block
        self.error_label.setText("")

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress:
            if ((event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Return) or
                    (event.modifiers() & Qt.MetaModifier and event.key() == Qt.Key_Return)):
                self.format_sql();
                return True
        return super().eventFilter(obj, event)

    def copy_output(self):
        QApplication.clipboard().setText(self.output_text.text())