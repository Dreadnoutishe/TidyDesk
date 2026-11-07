from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QMainWindow,
                               QMessageBox, QProgressBar, QScrollArea, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)
from app.services.operations import organize, recover, undo_last
from app.services.safety import check_root
from app.services.scanner import find_duplicates, preview, scan
from .duplicates import Duplicates
from .history import HistoryView
from .home import Home
from .organize import Organize
from .style import ASSETS, icon
from .widgets import button, details, fade, label
from .worker import Worker


class MainWindow(QMainWindow):
    def __init__(self, history, settings):
        super().__init__()
        self.history, self.settings = history, settings
        self.root = self.snapshot = self.job = None
        self.setWindowTitle("TidyDesk")
        self.setWindowIcon(QIcon(str(ASSETS / "mark.svg")))
        available = self.screen().availableGeometry()
        self.resize(min(1060, available.width() - 20), min(760, available.height() - 55))
        self.setMinimumSize(770, 520)
        base = QWidget()
        base.setObjectName("page")
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(72)
        h = QHBoxLayout(header)
        h.setContentsMargins(26, 0, 26, 0)
        brand_icon = label()
        brand_icon.setPixmap(QIcon(str(ASSETS / "mark.svg")).pixmap(38, 38))
        h.addWidget(brand_icon)
        h.addWidget(label("TidyDesk", "brand"))
        h.addStretch()
        self.tabs = QButtonGroup(self)
        self.tabs.setExclusive(True)
        for i, name in enumerate(("Home", "Organize", "Duplicates", "History")):
            tab = button(name, name)
            tab.setObjectName("nav")
            tab.setCheckable(True)
            self.tabs.addButton(tab, i)
            h.addWidget(tab)
        layout.addWidget(header)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        wrap = QWidget()
        outer = QHBoxLayout(wrap)
        outer.setContentsMargins(24, 20, 24, 18)
        outer.addStretch(1)
        column = QWidget()
        column.setMaximumWidth(1080)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(9)
        self.activity = label("", "muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.activity.hide()
        self.progress.hide()
        inner.addWidget(self.activity)
        inner.addWidget(self.progress)
        self.pages = QStackedWidget()
        self.home, self.org = Home(), Organize()
        self.dups, self.log = Duplicates(), HistoryView(history)
        for page in (self.home, self.org, self.dups, self.log):
            self.pages.addWidget(page)
        inner.addWidget(self.pages, 1)
        outer.addWidget(column, 100)
        outer.addStretch(1)
        self.scroll.setWidget(wrap)
        layout.addWidget(self.scroll)
        self.tabs.idClicked.connect(self.navigate)
        self.navigate(0)
        self.home.choose.clicked.connect(self.pick)
        self.home.scan.clicked.connect(self.scan_folder)
        self.home.issues.clicked.connect(lambda: details(self, "Skipped items", self.snapshot.issues))
        self.org.go.clicked.connect(self.confirm_organize)
        self.dups.refresh.clicked.connect(self.check_duplicates)
        self.log.undo.clicked.connect(self.confirm_undo)
        remembered = self.settings.value("folder", "")
        if remembered:
            self.select_folder(Path(remembered), save=False)
        self.log.refresh()
        if any(s["pending"] for s in history.sessions()):
            QTimer.singleShot(0, self.reconcile)

    def reconcile(self):
        self.start("Checking interrupted operations", lambda p, m: recover(self.history),
                   lambda _: self.log.refresh())

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        self.tabs.button(index).setChecked(True)
        self.scroll.verticalScrollBar().setValue(0)
        if index == 3:
            self.log.refresh()

    def pick(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a folder", str(self.root or Path.home()),
                                               QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        if path:
            self.select_folder(Path(path))

    def select_folder(self, root, save=True):
        try:
            check_root(root)
        except ValueError as error:
            if save:
                QMessageBox.warning(self, "Choose another folder", str(error))
            return
        self.root, self.snapshot = root, None
        self.home.set_folder(root)
        self.home.update_scan(None)
        self.org.load(None, [], [])
        self.org.result.clear()
        self.org.motion.hide()
        self.dups.clear(root)
        if save:
            self.settings.setValue("folder", str(root))

    def start(self, title, task, complete):
        if self.job:
            return
        self.callback = complete
        self.activity.setText(title)
        self.activity.show()
        self.progress.setRange(0, 0)
        self.progress.show()
        self.pages.setEnabled(False)
        self.job = Worker(task)
        self.job.progress.connect(self.show_progress)
        self.job.moved.connect(self.acknowledge)
        self.job.finished.connect(self.finished)
        self.job.start()

    def show_progress(self, value, total, text):
        self.activity.setText(text)
        self.progress.setRange(0, total)
        self.progress.setValue(value)

    def acknowledge(self, category, reverse):
        (self.log if reverse else self.org).motion.acknowledge(category, reverse)

    def finished(self):
        worker, callback = self.job, self.callback
        self.job = None
        self.pages.setEnabled(True)
        self.activity.hide()
        self.progress.hide()
        worker.deleteLater()
        if worker.error:
            self.log.refresh()
            QMessageBox.warning(self, "TidyDesk couldn’t finish", worker.error)
            return
        callback(worker.result)

    def scan_folder(self):
        if not self.root or self.job:
            return
        root = self.root

        def task(progress, moved):
            snapshot = scan(root, progress)
            return snapshot, *preview(snapshot)
        self.start("Scanning folder…", task, self.scanned)

    def scanned(self, result):
        self.snapshot, moves, issues = result
        self.home.update_scan(self.snapshot)
        self.org.load(self.snapshot, moves, self.snapshot.issues + issues)
        self.dups.clear(self.root)

    def check_duplicates(self):
        root = self.root
        if not root or self.job:
            return

        def task(progress, moved):
            snap = scan(root, progress)
            return snap, preview(snap), find_duplicates(snap, progress)

        def complete(result):
            snap, plan, matches = result
            self.scanned((snap, *plan))
            self.dups.show_results(root, *matches)
        self.start("Checking matching-size files…", task, complete)

    def ask(self, title, message, action):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(message)
        yes = dialog.addButton(action, QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        return dialog.clickedButton() == yes

    def confirm_organize(self):
        if self.job or not self.snapshot:
            return
        snap = self.snapshot
        moves = self.org.model.selected()
        if not moves or not self.ask("Organize files", f"Move {len(moves)} selected files into the "
                                    f"previewed category folders inside\n{snap.root}?", "Organize Files"):
            return
        self.org.result.clear()
        self.org.motion.hide()
        self.start("Preparing file moves…", lambda p, m: organize(self.history, snap, moves, p, m),
                   lambda result: self.completed(result, False))

    def confirm_undo(self):
        if self.job:
            return
        session = self.history.latest_undo()
        if not session or not self.ask("Undo last organization", f"Restore {session['available']} files "
                                      f"to their original names in\n{session['root']}?", "Restore files"):
            return
        self.log.result.clear()
        self.log.motion.hide()
        self.start("Checking files before restoring…",
                   lambda p, m: undo_last(self.history, session["id"], p, m),
                   lambda result: self.completed(result, True))

    def completed(self, result, undo):
        view = self.log if undo else self.org
        verb = "restored" if undo else "organized"
        count = f"{result.done} {'file' if result.done == 1 else 'files'} {verb}"
        if result.issues:
            view.result.setText(f"{count} · {len(result.issues)} skipped or unverified")
            details(self, "Files needing attention", result.issues)
        else:
            view.result.setText(f"✓  {count}." if undo else f"✓  All tidy!  {count}.")
            fade(view.result)
        self.log.refresh()
        self.snapshot = None
        self.org.load(None, [], [])
        self.home.update_scan(None)
        self.dups.clear(self.root)
        if self.root:
            self.scan_folder()

    def closeEvent(self, event):
        if self.job:
            self.activity.setText("Finishing the current task. You can close TidyDesk when it completes.")
            event.ignore()
        else:
            event.accept()

