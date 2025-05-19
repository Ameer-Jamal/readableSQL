# Readable SQL Formatter

A PyQt5-based GUI application that formats SQL `INSERT`, `UPDATE`, `SET`, and other blocks for improved readability.
Supports optional embedded JSON formatting with a toggle.

![img.png](img.png)

## Features

- Auto-detects block type: `INSERT ... VALUES`, `INSERT ... SELECT`, `SET`, `UPDATE`, `CREATE TABLE`, etc.
- Pretty-prints embedded JSON (toggleable)
- Syntax highlighting via QScintilla
- Ctrl+Enter / Cmd+Enter shortcut for formatting
- Copy-to-clipboard button
- Auto-installs dependencies if missing

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
