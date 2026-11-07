import ctypes
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGraphicsOpacityEffect,
                               QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)
from .style import icon


def label(text="", role=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    return widget


def card(role="card"):
    frame = QFrame()
    frame.setObjectName(role)
    return frame


def button(text, symbol=None, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    if symbol:
        widget.setIcon(icon(symbol, "#fff" if primary else "#74647f", 18))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def motion_enabled():
    value = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
    return bool(value.value)


def fade(widget, delay=0):
    if not motion_enabled():
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", effect)
    animation.setDuration(280 + delay)
    animation.setStartValue(0.05)
    if delay:
        animation.setKeyValueAt(delay / (280 + delay), 0.05)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    animation.start()


def details(parent, title, lines):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(640, 350)
    layout = QVBoxLayout(dialog)
    layout.addWidget(label(title, "section"))
    text = QPlainTextEdit()
    text.setReadOnly(True)
    text.setPlainText("\n".join(lines))
    layout.addWidget(text)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()

