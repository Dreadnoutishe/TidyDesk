from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QTableView, QVBoxLayout, QWidget)
from app.services.catalog import readable_size
from .motion import Journey
from .style import COLORS, icon
from .widgets import button, card, details, label

R = Qt.ItemDataRole


class PlanModel(QAbstractTableModel):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.moves = []
        self.excluded = set()
        self.root = None

    def reset(self, moves, root):
        self.beginResetModel()
        self.moves, self.root, self.excluded = moves, root, set()
        self.endResetModel()
        self.changed.emit()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.moves)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == R.DisplayRole:
            return ["Move", "File name", "Destination", "Size"][section]
        return None

    def data(self, index, role):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        move = self.moves[row]
        entry = move.entry
        destination = self.root / entry.group / move.target
        if role == R.CheckStateRole and col == 0:
            return Qt.CheckState.Unchecked if row in self.excluded else Qt.CheckState.Checked
        if role == R.DecorationRole and col == 1:
            return icon(entry.group, COLORS[entry.group][1], 16)
        if role == R.DisplayRole:
            return ["", entry.name, str(destination.relative_to(self.root)), readable_size(entry.size)][col]
        if role == R.ToolTipRole:
            return str(destination) if col == 2 else str(self.root / entry.name)
        return None

    def flags(self, index):
        flags = super().flags(index)
        return flags | Qt.ItemFlag.ItemIsUserCheckable if index.column() == 0 else flags

    def setData(self, index, value, role):
        if index.column() != 0 or role != R.CheckStateRole:
            return False
        if value == Qt.CheckState.Checked.value:
            self.excluded.discard(index.row())
        else:
            self.excluded.add(index.row())
        self.dataChanged.emit(index, index, [role])
        self.changed.emit()
        return True

    def selected(self):
        return [m for i, m in enumerate(self.moves) if i not in self.excluded]


class Organize(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(label("Organize files", "heading"))
        self.folder = label("Choose and scan a folder on Home to preview its moves.", "muted")
        self.folder.setWordWrap(True)
        layout.addWidget(self.folder)
        self.review = label("", "muted")
        self.review.setWordWrap(True)
        layout.addWidget(self.review)
        panel = card()
        col = QVBoxLayout(panel)
        col.setContentsMargins(18, 16, 18, 16)
        line = QHBoxLayout()
        line.addWidget(label("Move preview", "section"))
        line.addStretch()
        self.toggle = button("Deselect all")
        line.addWidget(self.toggle)
        col.addLayout(line)
        self.model = PlanModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setMinimumHeight(200)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(3, 88)
        col.addWidget(self.table)
        self.note = label("", "micro")
        self.note.setWordWrap(True)
        col.addWidget(self.note)
        self.issue_btn = button("Review skipped files")
        self.issue_btn.hide()
        col.addWidget(self.issue_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.issues = []
        self.issue_btn.clicked.connect(lambda: details(self, "Skipped files", self.issues))
        layout.addWidget(panel, 1)
        line = QHBoxLayout()
        self.go = button("Organize Files", "Organize", True)
        self.count = label("", "muted")
        line.addWidget(self.go)
        line.addWidget(self.count)
        line.addStretch()
        self.motion = Journey()
        line.addWidget(self.motion)
        layout.addLayout(line)
        self.result = label("", "section")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.toggle.clicked.connect(self.select_all)
        self.model.changed.connect(self.update_count)
        self.update_count()

    def select_all(self):
        select = bool(self.model.excluded)
        self.model.beginResetModel()
        self.model.excluded = set() if select else set(range(len(self.model.moves)))
        self.model.endResetModel()
        self.update_count()

    def update_count(self):
        count = len(self.model.moves) - len(self.model.excluded)
        self.count.setText(f"{count} selected")
        self.go.setEnabled(bool(count))
        self.toggle.setEnabled(bool(self.model.moves))
        self.toggle.setText("Select all" if self.model.excluded else "Deselect all")

    def load(self, snap, moves, issues):
        self.model.reset(moves, snap.root if snap else None)
        self.folder.setText(str(snap.root) if snap else "Choose and scan a folder on Home to preview its moves.")
        self.review.setText("  ·  ".join(dict.fromkeys(sorted(e.group for e in snap.files))) if snap else "")
        collisions = sum(m.entry.name != m.target for m in moves)
        self.note.setText(f"{collisions} renamed to avoid conflicts. Review the destination names."
                          if collisions else "Checked files will move into category folders inside this folder.")
        self.issues = issues
        self.issue_btn.setVisible(bool(issues))

