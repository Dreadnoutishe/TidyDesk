import json
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from app.database.history import status
from app.services.catalog import category
from .motion import Journey
from .widgets import button, details, label


class HistoryView(QWidget):
    def __init__(self, history):
        super().__init__()
        self.history = history
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(label("Organization history", "heading"))
        self.note = label("", "muted")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.list = QTreeWidget()
        self.list.setRootIsDecorated(False)
        self.list.setHeaderLabels(["When", "Original folder", "Moved", "Status", "Undo"])
        self.list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.list.setColumnWidth(0, 150)
        self.list.setColumnWidth(2, 62)
        self.list.setColumnWidth(3, 156)
        self.list.setMinimumHeight(220)
        self.list.setAlternatingRowColors(True)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.undo = button("Undo Last Organization", "History", True)
        self.detail = button("Session details")
        row.addWidget(self.undo)
        row.addWidget(self.detail)
        row.addStretch()
        self.motion = Journey()
        row.addWidget(self.motion)
        layout.addLayout(row)
        self.result = label("", "section")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.detail.clicked.connect(self.show_details)
        self.list.itemDoubleClicked.connect(self.show_details)

    def refresh(self):
        sessions = self.history.sessions()
        self.list.clear()
        for s in sessions:
            time = datetime.fromisoformat(s["created"]).strftime("%d %b %Y  %H:%M")
            item = QTreeWidgetItem([time, s["root"], f"{s['moved']}/{s['total']}",
                                    status(s), f"{s['available']} available" if s["available"] else "—"])
            item.setToolTip(1, s["root"])
            item.setData(0, Qt.ItemDataRole.UserRole, s["id"])
            self.list.addTopLevelItem(item)
        self.detail.setEnabled(bool(sessions))
        self.undo.setEnabled(any(s["available"] for s in sessions))
        if sessions:
            self.list.setCurrentItem(self.list.topLevelItem(0))
        self.note.setText("Review a session to see each file’s destination and restore status."
                          if sessions else "Your completed file moves will appear here, ready to review or undo.")

    def show_details(self):
        item = self.list.currentItem()
        if item:
            rows = self.history.rows(item.data(0, Qt.ItemDataRole.UserRole))
            lines = []
            for row in rows:
                entry = json.loads(row["entry"])
                lines.append(f"{entry['name']}  →  {category(entry['name'])}\\{row['target']}\n"
                             f"    {row['state'].capitalize()}   {row['note']}\n")
            details(self, "Session details", lines)

