from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QParallelAnimationGroup
from PySide6.QtWidgets import QFrame, QLabel, QGraphicsOpacityEffect

from .style import COLORS, icon
from .widgets import motion_enabled


class Journey(QFrame):
    """One visual acknowledgement of a verified move. Bursts share one flight."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(148, 60)
        self.setAccessibleName("File movement")
        self.setStyleSheet("Journey {background:#efe9f4;border-radius:10px;}")
        self.origin = QLabel(self)
        self.origin.setGeometry(9, 10, 28, 28)
        self.origin.setPixmap(icon("Documents").pixmap(26, 26))
        self.folder = QLabel(self)
        self.folder.setGeometry(112, 9, 31, 31)
        self.caption = QLabel(self)
        self.caption.setGeometry(6, 38, 136, 19)
        self.caption.setStyleSheet("font-size:8pt;color:#65546e;")
        self.file = QLabel(self)
        self.file.resize(22, 22)
        self.opacity = QGraphicsOpacityEffect(self.file)
        self.file.setGraphicsEffect(self.opacity)
        self.group = QParallelAnimationGroup(self)
        self.flight = QPropertyAnimation(self.file, b"pos")
        self.flight.setDuration(1050)
        self.flight.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.glow = QPropertyAnimation(self.opacity, b"opacity")
        self.glow.setDuration(1050)
        self.glow.setStartValue(0.1)
        self.glow.setKeyValueAt(0.25, 1.0)
        self.glow.setKeyValueAt(0.78, 1.0)
        self.glow.setEndValue(0.05)
        self.group.addAnimation(self.flight)
        self.group.addAnimation(self.glow)
        self.hide()

    def acknowledge(self, category, reverse):
        self.show()
        if self.group.state() == self.group.State.Running:
            return
        color = COLORS[category][1]
        self.caption.setText(f"{'Restoring from' if reverse else 'Moved to'} {category}")
        self.folder.setPixmap(icon("folder", color, 30).pixmap(30, 30))
        self.setToolTip(f"{'Restoring from' if reverse else 'Moved to'} {category}")
        self.file.setPixmap(icon(category, color, 20).pixmap(20, 20))
        a, b = QPoint(18, 16), QPoint(114, 16)
        self.flight.setStartValue(b if reverse else a)
        self.flight.setKeyValueAt(0.5, QPoint(66, 3))
        self.flight.setEndValue(a if reverse else b)
        if motion_enabled():
            self.group.start()
        else:
            self.file.move(64, 14)

