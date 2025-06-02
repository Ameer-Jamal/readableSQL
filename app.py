import subprocess
import sys
import logging

# --- Configuration ---
MIN_PYTHON = (3, 7)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Version Check ---
if sys.version_info < MIN_PYTHON:
    logging.critical(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or higher is required.")
    sys.exit(1)


# --- Dependency Management ---
def install_requirements():
    try:
        logging.info("Installing required packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logging.info("Installation complete.")
    except subprocess.CalledProcessError:
        logging.error("Failed to install requirements.")
        sys.exit(1)


def import_dependencies():
    try:
        from PyQt5 import QtWidgets
        from PyQt5.Qsci import QsciScintilla
        return QtWidgets
    except ImportError:
        install_requirements()
        try:
            from PyQt5 import QtWidgets
            from PyQt5.Qsci import QsciScintilla
            return QtWidgets
        except ImportError:
            logging.error("PyQt5 or QScintilla still not found after installation.")
            sys.exit(1)


# --- Main ---
def main():
    QtWidgets = import_dependencies()
    try:
        from gui_app import SQLFormatterApp
    except ImportError as e:
        logging.error(f"Failed to import GUI application: {e}")
        sys.exit(1)

    app = QtWidgets.QApplication(sys.argv)
    window = SQLFormatterApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
