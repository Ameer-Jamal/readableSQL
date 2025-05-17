import sys

from PyQt5.Qsci import QsciScintilla, QsciLexerSQL
from PyQt5.QtCore import Qt
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
        self._setup_ui()
        self._load_cached_input()
        self.installEventFilter(self)

    def _setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Paste raw SQL INSERT statement:"))

        # Input editor
        self.input_text = self._create_scintilla_editor(with_lexer=True)

        # Output editor
        self.output_text = self._create_scintilla_editor(with_lexer=True)

        # Splitter to allow resizing
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.input_text)
        splitter.addWidget(self.output_text)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

        # Format + Copy buttons
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

        # Pretty‐print JSON toggle
        json_row = QHBoxLayout()
        self.json_checkbox = QCheckBox("Pretty JSON")
        self.json_checkbox.setFont(self.mono)
        self.json_checkbox.setChecked(True)
        json_row.addWidget(self.json_checkbox)
        json_row.addStretch()
        layout.addLayout(json_row)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        self.setLayout(layout)

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

        pal = editor.palette()
        pal.setColor(QPalette.Base, QColor("#f0f0f0"))
        pal.setColor(QPalette.Text, QColor("#000000"))
        editor.setPalette(pal)

        if with_lexer:
            lexer = QsciLexerSQL()
            lexer.setDefaultFont(self.mono)
            lexer.setDefaultPaper(QColor("#f0f0f0"))
            lexer.setDefaultColor(QColor("#000000"))
            self._apply_lexer_theme(lexer)
            editor.setLexer(lexer)

        return editor

    def _apply_lexer_theme(self, lexer):
        for style in range(128):
            lexer.setFont(self.mono, style)
            lexer.setPaper(QColor("#f0f0f0"), style)  # force light background
            # Do NOT set foreground color! Keep default SQL colors

    def format_sql(self):
        sql = self.input_text.text()

        # Save input to cache
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write(sql)

        # pass checkbox state as pretty_json flag
        pretty = self.json_checkbox.isChecked()
        formatted = SQLFormatter.SQLFormatter.format_all(sql, pretty_json=pretty)
        if formatted.startswith("❌"):
            self.error_label.setText(formatted)
            self.output_text.setText("")
        else:
            self.error_label.setText("")
            self.output_text.setText(formatted)

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress:
            if ((event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Return) or
                    (event.modifiers() & Qt.MetaModifier and event.key() == Qt.Key_Return)):  # Cmd on macOS
                self.format_sql()
                return True  # handled
        return super().eventFilter(obj, event)

    def copy_output(self):
        QApplication.clipboard().setText(self.output_text.text())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SQLFormatterApp()
    window.show()
    sys.exit(app.exec_())
