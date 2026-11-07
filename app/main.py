import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QSettings, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.history import History
from app.ui.main_window import MainWindow
from app.ui.style import STYLE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TidyDesk")
    app.setOrganizationName("TidyDesk")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    try:
        data.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(data / "instance.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            QMessageBox.information(None, "TidyDesk", "TidyDesk is already open, or its history folder is unavailable.")
            return 1
        history = History(data / "history.sqlite")
        window = MainWindow(history, QSettings(str(data / "settings.ini"), QSettings.Format.IniFormat))
    except Exception as error:
        QMessageBox.critical(None, "TidyDesk could not start", str(error))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

