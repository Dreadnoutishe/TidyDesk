from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parents[2] / "assets"
COLORS = {
    "Images": ("#e5eee5", "#587761"), "Documents": ("#e2eaf5", "#58759a"),
    "Videos": ("#f1e4ef", "#9b7096"), "Audio": ("#f9e5d8", "#ac7458"),
    "Archives": ("#f7edcb", "#9a803b"), "Code": ("#e1eeeb", "#50857c"),
    "Installers": ("#eae3f5", "#8a71a3"), "Other": ("#ebe9e6", "#807a71"),
}
PATHS = {
    "Home": '<path d="m3 10 9-7 9 7v10h-6v-6H9v6H3z"/>',
    "folder": '<path d="M3 6h7l2 3h9v11H3z"/>',
    "Organize": '<path d="M3 5h6l2 2h10v12H3zM7 13h10m-3-3 3 3-3 3"/>',
    "Duplicates": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 5V3H4v13h2"/>',
    "History": '<path d="M3 10a9 9 0 1 1 1 8M3 4v6h6m3-4v6l4 3"/>',
    "Images": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="1.4"/><path d="m4 17 5-5 4 4 3-3 4 4"/>',
    "Documents": '<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h7m-7 4h6"/>',
    "Videos": '<rect x="3" y="5" width="18" height="15" rx="2"/><path d="m10 9 5 3.5-5 3z"/>',
    "Audio": '<path d="M9 17V6l11-3v11M9 9l11-3"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="17" cy="15" rx="3" ry="2.5"/>',
    "Archives": '<path d="M4 9h16v11H4zM3 4h18v5H3zM9 13h6"/>',
    "Code": '<path d="m7 7-5 5 5 5m10-10 5 5-5 5m-3-13-4 16"/>',
    "Installers": '<path d="M12 3v12m-4-4 4 4 4-4M4 16v4h16v-4"/>',
    "Other": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M7 12h1m3 0h1m3 0h1"/>',
    "scan": '<path d="M3 8V4h4m10 0h4v4m0 8v4h-4M7 20H3v-4m0-4h18"/>',
    "storage": '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M6 15h8m3 0h1"/>',
    "grid": '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "arrow": '<path d="M4 12h15m-6-6 6 6-6 6"/>',
}


@lru_cache(maxsize=128)
def icon(name, color="#685775", size=24):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           f'<g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{PATHS[name]}</g></svg>')
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


STYLE = """
QWidget {color:#332f38; font: 10pt 'Segoe UI';}
QMainWindow, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {background:#faf9f6;}
QLabel {background:transparent;}
QFrame#header {background:#fffefa; border-bottom:1px solid #e4dfdf;}
QLabel#brand {font: bold 19pt 'Georgia';color:#403647;}
QLabel#heading {font: 24pt 'Georgia';color:#3e3345;}
QLabel#section {font: bold 14pt 'Segoe UI';color:#403945;}
QLabel#eyebrow {font: bold 8pt 'Segoe UI'; color:#79628b;}
QLabel#muted {color:#706976;}
QLabel#micro {color:#79717d; font-size:9pt;}
QLabel#value {font: 21pt 'Georgia';color:#3d3444;}
QFrame#hero {background:#eee8f3;border:1px solid #ded4e6;border-radius:20px;}
QFrame#card, QFrame#category {background:#fffefa;border:1px solid #e4dfe1;border-radius:13px;}
QFrame#category:hover {border:1px solid #b39ac7;background:#fff;}
QFrame#bar {background:#eee9e7;border-radius:3px;}
QPushButton {background:#fffefa;border:1px solid #d9d1db;border-radius:8px;padding:8px 14px;color:#52465c;font-weight:600;}
QPushButton:hover {background:#f3edf6;border-color:#b7a4c4;}
QPushButton:pressed {background:#e5dbea;}
QPushButton#primary {background:#705787;border-color:#705787;color:white;}
QPushButton#primary:hover {background:#604973;}
QPushButton:disabled {background:#ede9ec;color:#89818d;border-color:#ded9df;}
QPushButton#nav {background:transparent;color:#6a626d;border:0;padding:8px 15px;}
QPushButton#nav:hover {background:#f5f1f7;}
QPushButton#nav:checked {background:#eae2f1;color:#614777;}
QPushButton:focus {border:2px solid #997bb2;}
QTableView,QTreeWidget,QListWidget,QPlainTextEdit {background:#fffefa;alternate-background-color:#faf8fb;border:1px solid #e0dadf;border-radius:9px;selection-background-color:#e7def0;selection-color:#332d38;}
QHeaderView::section {background:#f3eff3;color:#6d6074;border:none;padding:8px;text-align:left;font-weight:600;}
QTreeWidget::item,QListWidget::item {padding:7px;}
QProgressBar {border:0;background:#e9e2ec;border-radius:3px;max-height:5px;}
QProgressBar::chunk {background:#a287b5;border-radius:3px;}
QToolTip {background:#43384b;color:white;border:0;padding:5px;}
QScrollBar:vertical {width:9px;background:transparent;}
QScrollBar::handle:vertical {background:#d6ced8;border-radius:4px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
"""

