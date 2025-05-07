import sys
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QPushButton, QLabel, QSizePolicy
)
from PyQt5.Qsci import QsciScintilla, QsciLexerSQL
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt


class InsertFormatter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL Insert Formatter")
        self.setMinimumSize(900, 650)

        # Larger monospace font
        mono = QFont("Courier New", 14)
        mono.setStyleHint(QFont.Monospace)

        layout = QVBoxLayout()

        # Input label
        self.input_label = QLabel("Paste raw SQL INSERT statement:")
        layout.addWidget(self.input_label)

        # Input editor with SQL lexer
        self.input_text = QsciScintilla()
        self.input_text.setFont(mono)
        self.input_text.setUtf8(True)
        lexer_in = QsciLexerSQL()
        lexer_in.setDefaultFont(mono)
        lexer_in.setDefaultPaper(QColor("#f0f0f0"))
        lexer_in.setDefaultColor(QColor("#000000"))
        self.input_text.setLexer(lexer_in)
        pal_in = self.input_text.palette()
        pal_in.setColor(QPalette.Base, QColor("#f0f0f0"))
        pal_in.setColor(QPalette.Text, QColor("#000000"))
        self.input_text.setPalette(pal_in)
        self.input_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.input_text)

        # Format button
        self.format_button = QPushButton("Format")
        self.format_button.setFont(mono)
        self.format_button.clicked.connect(self.format_sql)
        layout.addWidget(self.format_button)

        # Output label
        self.output_label = QLabel("Formatted SQL with Inline Comments:")
        layout.addWidget(self.output_label)

        # Output editor
        self.output_text = QsciScintilla()
        self.output_text.setFont(mono)
        self.output_text.setUtf8(True)
        lexer_out = QsciLexerSQL()
        lexer_out.setDefaultFont(mono)
        lexer_out.setDefaultPaper(QColor("#f0f0f0"))
        lexer_out.setDefaultColor(QColor("#000000"))
        self.output_text.setLexer(lexer_out)
        pal_out = self.output_text.palette()
        pal_out.setColor(QPalette.Base, QColor("#f0f0f0"))
        pal_out.setColor(QPalette.Text, QColor("#000000"))
        self.output_text.setPalette(pal_out)
        self.output_text.setReadOnly(True)
        self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.output_text)

        self.setLayout(layout)

    def format_sql(self):
        sql = self.input_text.text()
        # Capture table name dynamically
        table_m = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql, re.IGNORECASE)
        cols_m  = re.search(r"INSERT\s+INTO\s+[^\s(]+\s*\((.*?)\)\s*VALUES", sql, re.DOTALL | re.IGNORECASE)
        vals_m  = re.search(r"VALUES\s*\(\s*(.*?)\s*\)\s*;", sql, re.DOTALL | re.IGNORECASE)

        if not table_m or not cols_m or not vals_m:
            self.output_text.setText("❌ Invalid format. Expecting INSERT INTO <table>(...) VALUES (...);")
            return

        table_name = table_m.group(1)
        cols       = [c.strip() for c in cols_m.group(1).split(',')]
        vals       = [v.strip() for v in re.split(r',(?![^()]*\))', vals_m.group(1))]

        if len(cols) != len(vals):
            self.output_text.setText(f"❌ Column/value count mismatch ({len(cols)} vs {len(vals)}).")
            return

        # Align on longest column
        width = max(len(c) for c in cols)
        lines = [f"INSERT INTO {table_name} ("]
        for i, c in enumerate(cols):
            comma = ',' if i < len(cols) - 1 else ''
            lines.append(f"    {c.ljust(width)}{comma}")
        lines.append(") VALUES (")
        for i, v in enumerate(vals):
            comma = ',' if i < len(vals) - 1 else ''
            lines.append(f"    {v.ljust(width)}{comma}  -- {cols[i]}")
        lines.append(");")

        self.output_text.setText("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InsertFormatter()
    window.show()
    sys.exit(app.exec_())
