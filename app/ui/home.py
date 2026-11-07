from collections import Counter
from PySide6.QtCore import Qt, QSize
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QSizePolicy,
                               QVBoxLayout, QWidget)
from PySide6.QtGui import QColor, QPainter
from app.services.catalog import EXTENSIONS, readable_size
from app.services.scanner import by_size
from .style import ASSETS, COLORS, icon
from .widgets import button, card, fade, label


class StorageBar(QWidget):
    def __init__(self):
        super().__init__()
        self.values = {}
        self.setFixedHeight(6)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e7e2e4"))
        p.drawRoundedRect(self.rect(), 3, 3)
        total = sum(self.values.values())
        offset = 0
        if total:
            for group in COLORS:
                width = self.width() * self.values.get(group, 0) / total
                if width:
                    p.setBrush(QColor(COLORS[group][1]).lighter(132))
                    p.drawRoundedRect(round(offset), 0, max(1, round(width)-1), 6, 2, 2)
                    offset += width
        p.end()


def medallion(symbol, bg, ink, side=36):
    w = label()
    w.setFixedSize(side, side)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setStyleSheet(f"background:{bg};border-radius:10px;")
    w.setPixmap(icon(symbol, ink, 20).pixmap(20, 20))
    return w


class Home(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        hero = card("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 20, 14, 20)
        copy = QVBoxLayout()
        copy.setSpacing(7)
        copy.addWidget(label("FOLDER ORGANIZER", "eyebrow"))
        title = label()
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setText("Make your folders<br>feel a <i>little lighter.</i>")
        title.setStyleSheet("font: 28pt 'Georgia'; color:#493852;")
        copy.addWidget(title)
        actions = QHBoxLayout()
        self.choose = button("Choose a Folder", "folder", True)
        self.scan = button("Scan Folder", "scan")
        self.scan.setEnabled(False)
        actions.addWidget(self.choose)
        actions.addWidget(self.scan)
        actions.addStretch()
        copy.addSpacing(4)
        copy.addLayout(actions)
        self.path = label("Choose a local folder to get started.", "micro")
        self.path.setMinimumWidth(0)
        self.path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.full_path = ""
        copy.addWidget(self.path)
        hero_layout.addLayout(copy, 5)
        self.art = QSvgWidget(str(ASSETS / "desk.svg"))
        self.art.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.art.setMinimumSize(170, 135)
        self.art.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        hero_layout.addWidget(self.art, 4)
        layout.addWidget(hero)
        summary = QHBoxLayout()
        summary.addWidget(label("Folder overview", "section"))
        summary.addStretch()
        self.summary_note = label("Awaiting scan", "micro")
        summary.addWidget(self.summary_note)
        layout.addLayout(summary)
        line = QHBoxLayout()
        line.setSpacing(10)
        self.values = []
        for name, symbol, bg, ink in [
            ("Total files", "Documents", "#eee6f4", "#8a719d"),
            ("Storage used", "storage", "#e3eee8", "#688c79"),
            ("Categories", "grid", "#f6e7d9", "#ae805c"),
            ("Possible duplicate groups", "Duplicates", "#e5eaf4", "#778caf")]:
            box = card()
            col = QVBoxLayout(box)
            col.setContentsMargins(14, 12, 14, 12)
            col.setSpacing(5)
            top = QHBoxLayout()
            value = label("—", "value")
            top.addWidget(value)
            top.addStretch()
            top.addWidget(medallion(symbol, bg, ink, 29))
            col.addLayout(top)
            col.addWidget(label(name, "micro"))
            line.addWidget(box, 1)
            self.values.append(value)
        layout.addLayout(line)
        categories = QHBoxLayout()
        categories.addWidget(label("File categories", "section"))
        categories.addStretch()
        self.legend = label("8 file types", "micro")
        categories.addWidget(self.legend)
        layout.addLayout(categories)
        self.bar = StorageBar()
        layout.addWidget(self.bar)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.groups = {}
        for i, (name, (bg, ink)) in enumerate(COLORS.items()):
            box = card("category")
            row = QHBoxLayout(box)
            row.setContentsMargins(12, 12, 10, 12)
            row.addWidget(medallion(name, bg, ink))
            col = QVBoxLayout()
            col.setSpacing(2)
            heading = label(name)
            heading.setStyleSheet("font-weight:600;")
            col.addWidget(heading)
            sub = label(" · ".join(EXTENSIONS[name].split()[:3]).upper() or "Unlisted types", "micro")
            col.addWidget(sub)
            row.addLayout(col, 1)
            self.groups[name] = (box, sub)
            grid.addWidget(box, i // 4, i % 4)
        for i in range(4):
            grid.setColumnStretch(i, 1)
        layout.addLayout(grid)
        self.issues = button("View skipped items")
        self.issues.hide()
        layout.addWidget(self.issues, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

    def set_folder(self, root):
        self.full_path = str(root)
        self.fit_path()
        self.path.setToolTip(str(root))
        self.scan.setEnabled(True)
        fade(self.art)

    def fit_path(self):
        if self.full_path:
            self.path.setText(self.path.fontMetrics().elidedText(
                self.full_path, Qt.TextElideMode.ElideMiddle, min(390, max(180, self.path.width()))))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_path()

    def update_scan(self, snapshot):
        files = snapshot.files if snapshot else []
        counts = Counter(e.group for e in files)
        sizes = Counter()
        for entry in files:
            sizes[entry.group] += entry.size
        values = [str(len(files)), readable_size(sum(sizes.values())), str(len(counts)),
                  str(len(by_size(files)))]
        for w, value in zip(self.values, values):
            w.setText(value if snapshot else "—")
        for i, (name, (box, sub)) in enumerate(self.groups.items()):
            if snapshot:
                count = counts[name]
                sub.setText(f"{count} {'file' if count == 1 else 'files'} · {readable_size(sizes[name])}")
                fade(box, i * 30)
            else:
                sub.setText(" · ".join(EXTENSIONS[name].split()[:3]).upper() or "Unlisted types")
        self.summary_note.setText("Top-level files only" if snapshot else "Awaiting scan")
        if snapshot and snapshot.drive_free is not None:
            self.values[1].setToolTip(f"{readable_size(snapshot.drive_free)} free on this drive")
        self.bar.values = sizes
        self.bar.update()
        self.issues.setVisible(bool(snapshot and snapshot.issues))

