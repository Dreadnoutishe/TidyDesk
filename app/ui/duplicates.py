from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QHeaderView, QTreeView,
                               QVBoxLayout, QWidget)
from app.services.catalog import readable_size
from app.services.scanner import extra_bytes
from .style import icon
from .widgets import button, details, label

R = Qt.ItemDataRole


class DuplicateModel(QAbstractItemModel):
    def __init__(self):
        super().__init__()
        self.root = None
        self.groups = []

    def load(self, root, groups):
        self.beginResetModel()
        self.root, self.groups = root, groups
        self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column, parent.row() + 1 if parent.isValid() else 0)

    def parent(self, index):
        if index.isValid() and index.internalId():
            return self.createIndex(index.internalId() - 1, 0, 0)
        return QModelIndex()

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.groups)
        if parent.internalId() == 0 and parent.column() == 0:
            return len(self.groups[parent.row()])
        return 0

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, col, orientation, role):
        if role == R.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ["Matching files", "Size per copy", "Extra storage"][col]

    def path(self, index):
        if index.isValid() and index.internalId():
            return self.root / self.groups[index.internalId()-1][index.row()].name

    def data(self, index, role):
        if not index.isValid():
            return None
        path = self.path(index)
        if path:
            entry = self.groups[index.internalId()-1][index.row()]
            if role == R.DisplayRole:
                return [str(path), readable_size(entry.size), ""][index.column()]
            if role == R.ToolTipRole:
                return str(path)
        else:
            g = self.groups[index.row()]
            if role == R.DisplayRole:
                return [f"{g[0].name}   ·   {len(g)} copies", readable_size(g[0].size),
                        readable_size(extra_bytes(g))][index.column()]
            if role == R.BackgroundRole:
                return QColor("#f0eaf4")
            if role == R.DecorationRole and index.column() == 0:
                return icon("Duplicates", size=16)
        return None


class Duplicates(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(label("Find duplicates", "heading"))
        layout.addWidget(label("Compare matching-size files by their SHA-256 fingerprints.", "muted"))
        line = QHBoxLayout()
        self.refresh = button("Find duplicates", "scan", True)
        self.info = label("Choose a folder on Home first.", "muted")
        self.info.setWordWrap(True)
        line.addWidget(self.refresh)
        line.addWidget(self.info, 1)
        layout.addLayout(line)
        self.tree = QTreeView()
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumHeight(250)
        self.tree.setStyleSheet("QTreeView{background:#fffefa;border:1px solid #e4dfe1;border-radius:10px;}QTreeView::item{height:38px;}")
        self.model = DuplicateModel()
        self.tree.setModel(self.model)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)
        tools = QHBoxLayout()
        self.open = button("Open containing folder", "folder")
        self.copy = button("Copy path", "Duplicates")
        self.issues_btn = button("View skipped items")
        for w in (self.open, self.copy, self.issues_btn):
            tools.addWidget(w)
        tools.addStretch()
        layout.addLayout(tools)
        self.copy.clicked.connect(self.copy_path)
        self.open.clicked.connect(self.open_folder)
        self.tree.selectionModel().currentChanged.connect(self.update_controls)
        self.issues_btn.clicked.connect(lambda: details(self, "Skipped items", self.issues))
        self.clear(None)

    def clear(self, root):
        self.model.load(root, [])
        self.issues = []
        self.issues_btn.hide()
        self.refresh.setEnabled(bool(root))
        self.refresh.setText("Find duplicates")
        self.info.setText(str(root) if root else "Choose a folder on Home first.")
        self.update_controls()

    def show_results(self, root, groups, issues):
        self.model.load(root, groups)
        wasted = sum(extra_bytes(g) for g in groups)
        self.info.setText(f"{len(groups)} matching groups · {readable_size(wasted)} in extra copies"
                          if groups else "No identical copies found among the checked files.")
        self.refresh.setText("Refresh matches")
        self.issues = issues
        self.issues_btn.setVisible(bool(issues))
        self.update_controls()

    def update_controls(self):
        available = bool(self.model.path(self.tree.currentIndex()))
        self.copy.setEnabled(available)
        self.open.setEnabled(available)

    def copy_path(self):
        path = self.model.path(self.tree.currentIndex())
        if path:
            QApplication.clipboard().setText(str(path))

    def open_folder(self):
        path = self.model.path(self.tree.currentIndex())
        if path and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
            self.info.setText("Windows could not open the containing folder.")

