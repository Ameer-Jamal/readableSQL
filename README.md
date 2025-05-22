# Readable SQL Formatter

A PyQt5-based GUI application designed to format various SQL statements for enhanced readability and consistency.

![img.png](img.png)

--- 
## Features

- **Comprehensive SQL Block Formatting**:
    - `INSERT ... VALUES` (single and multi-row, with per-value comments)
    - `INSERT ... SELECT` (with per-select-item comments)
    - `UPDATE ... SET`
    - `SET @variable = ...`
    - `CREATE TABLE`
    - `ALTER TABLE`
    - `DELETE FROM`
    - `DROP TABLE / INDEX`
- **Intelligent JSON Handling**:
    - Pretty-prints embedded JSON strings within `UPDATE` statements (toggleable).
- **User-Friendly Interface**:
    - Syntax highlighting for SQL in both input and output editors via QScintilla.
    - **Dark Mode / Light Mode**: Toggleable theme for user preference.
    - **Drag and Drop**: Drop `.sql` or `.txt` files directly onto the input editor to load their content.
    - Editable input and output text areas.
- **Persistent Settings**:
    - Remembers your Dark Mode and Pretty JSON preferences between sessions.
    - Remembers window size/position and splitter position.
- **Convenience**:
    - **Auto-Format on Startup**: If cached input exists from a previous session, it's automatically formatted.
    - Ctrl+Enter / Cmd+Enter shortcut to trigger formatting.
    - "Copy Output" button for easy sharing.
- **Error Handling**:
    - Displays formatting errors directly within the output block, allowing continuation with other statements.
- **Dependency Management**:
    - Auto-installs `PyQt5` and `QScintilla` if they are missing when running `app.py`.

---

## Setup

```bash
git clone https://github.com/Ameer-Jamal/readableSQL.git
# Or:
gh repo clone Ameer-Jamal/readableSQL

cd readableSQL

# (Optional) Use Python 3.12
pyenv local 3.12.0

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the App

```bash
python app.py
```

> ✅ This will auto-install requirements if missing and launch the GUI.

---

## Running Tests

```bash
pytest
```

---

## Requirements

- Python 3.12
- `PyQt5>=5.15`
- `QScintilla>=2.13`

See `requirements.txt` for exact versions.
