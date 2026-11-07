from time import monotonic
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    progress = Signal(int, int, str)
    moved = Signal(str, bool)

    def __init__(self, task):
        super().__init__()
        self.task = task
        self.result = None
        self.error = ""
        self.last_update = 0

    def report(self, value, total, message):
        now = monotonic()
        if now - self.last_update > 0.08 or (total and value == total):
            self.last_update = now
            self.progress.emit(value, total, message)

    def run(self):
        try:
            self.result = self.task(self.report, self.moved.emit)
        except Exception as error:
            self.error = str(error) or type(error).__name__

