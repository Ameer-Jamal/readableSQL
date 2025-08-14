import os
import subprocess
import sys
import logging
import importlib

# --- Configuration ---
MIN_PYTHON = (3, 7)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# --- Version Check ---
if sys.version_info < MIN_PYTHON:
    logging.critical(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or higher is required.")
    sys.exit(1)


# --- Dependency Management ---
REQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")

def install_requirements():
    try:
        logging.info("Installing required packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQ_FILE])
        logging.info("Installation complete.")
    except subprocess.CalledProcessError:
        logging.error("Failed to install requirements.")
        sys.exit(1)

def safe_import(module_name, package_hint=None):
    """
    Try importing a module; if missing, install requirements and retry once.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError:
        logging.warning(f"Missing dependency: {module_name}. Attempting to install requirements...")
        install_requirements()
        try:
            return importlib.import_module(module_name)
        except ImportError as e:
            hint = f" (pip install {package_hint or module_name})" if package_hint else ""
            logging.critical(f"Still cannot import {module_name}{hint}: {e}")
            sys.exit(1)

def import_dependencies():
    # Ensure GUI deps
    safe_import("PyQt5")
    safe_import("PyQt5.Qsci")
    from PyQt5 import QtWidgets
    return QtWidgets


# --- Main ---
def main():
    QtWidgets = import_dependencies()

    try:
        from gui_app import SQLFormatterApp
    except ImportError as e:
        logging.error(f"Failed to import GUI application: {e}")
        sys.exit(1)

    # Lazy import version + checker after deps are present (avoids early ImportError)
    try:
        from version import __version__
    except Exception:
        __version__ = "0.0.0"
        logging.warning("version.py not found; defaulting to 0.0.0")

    try:
        from version_checker import VersionChecker
    except ImportError:
        install_requirements()
        from version_checker import VersionChecker

    app = QtWidgets.QApplication(sys.argv)
    window = SQLFormatterApp()
    window.show()

    # Optional: prompt user to update (non-blocking if no update)
    try:
        VersionChecker(__version__).prompt_update(parent=window)
    except Exception as e:
        logging.warning(f"Version check failed (continuing): {e}")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
