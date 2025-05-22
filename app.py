import subprocess
import sys

# Auto-install dependencies
try:
    from PyQt5 import QtWidgets
    from PyQt5.Qsci import QsciScintilla
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    # Try again after installing
    from PyQt5 import QtWidgets
    from PyQt5.Qsci import QsciScintilla

from gui_app import SQLFormatterApp
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SQLFormatterApp()

    window.show()
    sys.exit(app.exec_())
