"""
ui/dashboard.py - Main dashboard for Secure File Vault.

Professional dark-themed file-manager UI (indigo/slate palette).
All backend connections (database, file_manager, encryption) are preserved.
Includes auto-lock after 5 minutes of inactivity.
"""

from __future__ import annotations

import os
from functools import partial

from PyQt6.QtCore import Qt, QTimer, QEvent, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QStackedWidget,
    QFrame,
    QAbstractItemView,
    QProgressBar,
    QSizePolicy,
    QApplication,
)

from cryptography.fernet import Fernet

import database
import file_manager
from encryption import get_fernet


# ── Colour palette ───────────────────────────────────────────────────────────

C_BG       = "#0f172a"
C_PANEL    = "#1e293b"
C_SIDEBAR  = "#020617"
C_ACCENT   = "#6366f1"
C_ACCENT_H = "#818cf8"
C_TEXT     = "#e2e8f0"
C_TEXT2    = "#94a3b8"
C_BORDER   = "#334155"
C_SUCCESS  = "#22c55e"
C_WARN     = "#f59e0b"
C_DANGER   = "#ef4444"
C_VIEW     = "#8b5cf6"
C_VIEW_H   = "#a78bfa"
C_DEC      = "#3b82f6"
C_DEC_H    = "#60a5fa"
C_ROW_ALT  = "#162033"

# ── File-type helpers ────────────────────────────────────────────────────────

_FCOLORS = {
    "pdf": "#ef4444", "doc": "#3b82f6", "docx": "#3b82f6",
    "xls": "#22c55e", "xlsx": "#22c55e", "csv": "#22c55e",
    "ppt": "#f59e0b", "pptx": "#f59e0b",
    "png": "#ec4899", "jpg": "#ec4899", "jpeg": "#ec4899",
    "gif": "#ec4899", "svg": "#ec4899", "bmp": "#ec4899",
    "zip": "#a855f7", "rar": "#a855f7", "7z": "#a855f7",
    "txt": "#94a3b8", "py": "#22d3ee", "js": "#facc15",
    "mp3": "#f472b6", "mp4": "#f472b6", "wav": "#f472b6",
}

_FTYPES = {
    "pdf": "PDF", "doc": "Document", "docx": "Document",
    "xls": "Spreadsheet", "xlsx": "Spreadsheet", "csv": "CSV",
    "ppt": "Presentation", "pptx": "Presentation",
    "png": "Image", "jpg": "Image", "jpeg": "Image",
    "gif": "Image", "svg": "Image", "bmp": "Image",
    "zip": "Archive", "rar": "Archive", "7z": "Archive",
    "txt": "Text", "py": "Python", "js": "JavaScript",
    "mp3": "Audio", "mp4": "Video", "wav": "Audio",
}


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _ftype(name: str) -> str:
    e = _ext(name)
    return _FTYPES.get(e, e.upper() if e else "File")


def _icon_pm(ext: str, sz: int = 48) -> QPixmap:
    c = _FCOLORS.get(ext, C_ACCENT)
    pm = QPixmap(sz, sz)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(c))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, sz, sz, 10, 10)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", max(9, sz // 5), QFont.Weight.Bold))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter,
               ext[:4].upper() if ext else "FILE")
    p.end()
    return pm


# ── Reusable stylesheet fragments ───────────────────────────────────────────

_SB_BTN = """
QPushButton {{
    background-color: {bg}; color: {fg};
    border: none; border-radius: 10px;
    text-align: left; padding: 11px 18px;
    font-size: 13px; font-family: 'Segoe UI';
}}
QPushButton:hover {{ background-color: {hov}; }}
"""

_TBL = f"""
QTableWidget {{
    background-color: {C_PANEL}; color: {C_TEXT};
    border: none; border-radius: 12px;
    gridline-color: {C_BORDER}; font-size: 13px;
    font-family: 'Segoe UI'; outline: 0;
}}
QTableWidget::item {{
    padding: 8px 6px; border-bottom: 1px solid {C_BORDER};
}}
QTableWidget::item:selected {{ background-color: #253352; }}
QHeaderView::section {{
    background-color: {C_PANEL}; color: {C_TEXT2};
    border: none; border-bottom: 1px solid {C_BORDER};
    padding: 10px 8px; font-weight: 600;
    font-size: 12px; font-family: 'Segoe UI';
}}
QScrollBar:vertical {{
    background: {C_PANEL}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

_ABTN = """
QPushButton {{
    background-color: {bg}; color: white;
    border: none; border-radius: 6px;
    padding: 5px 14px; font-size: 11px;
    font-weight: 600; font-family: 'Segoe UI';
}}
QPushButton:hover {{ background-color: {hov}; }}
"""

_SEARCH = f"""
QLineEdit {{
    background-color: {C_PANEL}; color: {C_TEXT};
    border: 1px solid {C_BORDER}; border-radius: 10px;
    padding: 8px 14px 8px 14px; font-size: 13px;
    font-family: 'Segoe UI';
}}
QLineEdit:focus {{ border: 1px solid {C_ACCENT}; }}
"""

_PROG = f"""
QProgressBar {{
    background-color: {C_PANEL}; border: none; border-radius: 2px;
}}
QProgressBar::chunk {{
    background-color: {C_ACCENT}; border-radius: 2px;
}}
"""

AUTO_LOCK_MS = 5 * 60 * 1000


# ═════════════════════════════════════════════════════════════════════════════

class Dashboard(QWidget):
    """Main dashboard shown after successful authentication."""

    logout_requested = pyqtSignal()

    def __init__(self, password: str, salt: bytes) -> None:
        super().__init__()
        self._password = password
        self._salt = salt
        self._fernet: Fernet = get_fernet(password, salt)
        self._search_text = ""
        self._init_ui()
        self._setup_auto_lock()
        self._navigate(0)

    # ── UI skeleton ──────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        self.setStyleSheet(f"background-color: {C_BG};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._mk_sidebar())

        right = QWidget()
        right.setStyleSheet(f"background-color: {C_BG};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._mk_topbar())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {C_BG};")
        self._stack.addWidget(self._pg_dashboard())   # 0
        self._stack.addWidget(self._pg_files())        # 1
        self._stack.addWidget(self._pg_activity())     # 2
        self._stack.addWidget(self._pg_settings())     # 3
        rl.addWidget(self._stack, stretch=1)

        root.addWidget(right, stretch=1)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _mk_sidebar(self) -> QFrame:
        f = QFrame(); f.setObjectName("sb"); f.setFixedWidth(220)
        f.setStyleSheet(f"QFrame#sb{{background-color:{C_SIDEBAR};border-right:1px solid #1e293b;}}")
        ly = QVBoxLayout(f); ly.setContentsMargins(14, 24, 14, 20); ly.setSpacing(4)

        # brand
        br = QHBoxLayout()
        bi = QLabel("\U0001F6E1\uFE0F"); bi.setFont(QFont("Segoe UI Emoji", 18))
        bi.setStyleSheet("color:white;")
        bn = QLabel("Secure Vault"); bn.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        bn.setStyleSheet(f"color:{C_TEXT};")
        br.addWidget(bi); br.addWidget(bn); br.addStretch()
        ly.addLayout(br); ly.addSpacing(28)

        sec = QLabel("MENU"); sec.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        sec.setStyleSheet(f"color:{C_TEXT2};padding-left:8px;"); ly.addWidget(sec); ly.addSpacing(4)

        self._nav_btns: list[QPushButton] = []
        for label, idx in [
            ("\U0001F4CA  Dashboard", 0),
            ("\U0001F512  Vault Files", 1),
            ("\U0001F4DC  Activity Log", 2),
            ("\u2699\uFE0F  Settings", 3),
        ]:
            b = QPushButton(label); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(QFont("Segoe UI", 12)); b.setFixedHeight(42)
            b.clicked.connect(partial(self._navigate, idx))
            self._nav_btns.append(b); ly.addWidget(b)

        ly.addStretch()

        lo = QPushButton("\U0001F6AA  Logout"); lo.setCursor(Qt.CursorShape.PointingHandCursor)
        lo.setFont(QFont("Segoe UI", 12)); lo.setFixedHeight(42)
        lo.setStyleSheet(_SB_BTN.format(bg="transparent", fg=C_DANGER, hov="#1c1c2e"))
        lo.clicked.connect(self._logout); ly.addWidget(lo)
        return f

    # ── Top bar ──────────────────────────────────────────────────────────────

    def _mk_topbar(self) -> QFrame:
        bar = QFrame(); bar.setFixedHeight(64)
        bar.setStyleSheet(f"QFrame{{background-color:{C_PANEL};border-bottom:1px solid {C_BORDER};}}")
        ly = QHBoxLayout(bar); ly.setContentsMargins(28, 0, 28, 0)

        t = QLabel("Secure File Vault"); t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C_TEXT};border:none;"); ly.addWidget(t); ly.addStretch()

        sw = QWidget(); sw.setFixedWidth(300); sw.setStyleSheet("border:none;")
        sl = QHBoxLayout(sw); sl.setContentsMargins(0, 0, 0, 0)
        self._search = QLineEdit(); self._search.setPlaceholderText("\U0001F50D  Search files\u2026")
        self._search.setFixedHeight(38); self._search.setStyleSheet(_SEARCH)
        self._search.textChanged.connect(self._on_search); sl.addWidget(self._search)
        ly.addWidget(sw); ly.addStretch()

        av = QPushButton("\U0001F464"); av.setFont(QFont("Segoe UI Emoji", 16))
        av.setFixedSize(38, 38); av.setCursor(Qt.CursorShape.PointingHandCursor)
        av.setStyleSheet(f"QPushButton{{background-color:{C_BORDER};border:none;border-radius:19px;color:{C_TEXT};}}QPushButton:hover{{background-color:{C_ACCENT};}}")
        ly.addWidget(av)
        return bar

    # ── Page: Dashboard ──────────────────────────────────────────────────────

    def _pg_dashboard(self) -> QWidget:
        pg = QWidget(); ly = QVBoxLayout(pg)
        ly.setContentsMargins(28, 24, 28, 16); ly.setSpacing(20)

        # stat cards
        sr = QHBoxLayout(); sr.setSpacing(16)
        files = database.get_all_files(); logs = database.get_all_logs()
        for t, v, ic, c in [
            ("Total Files", str(len(files)), "\U0001F4C1", C_ACCENT),
            ("Encrypted", str(len(files)), "\U0001F512", C_SUCCESS),
            ("Activity Logs", str(len(logs)), "\U0001F4DC", C_WARN),
            ("Vault Status", "Locked \U0001F7E2", "\U0001F6E1\uFE0F", "#06b6d4"),
        ]:
            sr.addWidget(self._stat_card(t, v, ic, c))
        ly.addLayout(sr)

        # recent header
        rh = QHBoxLayout()
        rl = QLabel("Recent Files"); rl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        rl.setStyleSheet(f"color:{C_TEXT};"); rh.addWidget(rl); rh.addStretch()
        ub = self._accent_btn("\u2B06  Upload File"); ub.clicked.connect(self._upload_file)
        rh.addWidget(ub); ly.addLayout(rh)

        # progress
        self._prog = QProgressBar(); self._prog.setFixedHeight(4)
        self._prog.setRange(0, 0); self._prog.setStyleSheet(_PROG); self._prog.hide()
        ly.addWidget(self._prog)

        # recent grid
        self._rc_w = QWidget()
        self._rc_grid = QGridLayout(self._rc_w)
        self._rc_grid.setSpacing(14); self._rc_grid.setContentsMargins(0, 0, 0, 0)
        ly.addWidget(self._rc_w)

        # all files header
        ah = QHBoxLayout()
        al = QLabel("All Files"); al.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        al.setStyleSheet(f"color:{C_TEXT};"); ah.addWidget(al); ah.addStretch()
        ly.addLayout(ah)

        self._tbl = self._mk_table(); ly.addWidget(self._tbl, stretch=1)
        self._refresh_dash()
        return pg

    # ── Page: Vault Files ────────────────────────────────────────────────────

    def _pg_files(self) -> QWidget:
        pg = QWidget(); ly = QVBoxLayout(pg)
        ly.setContentsMargins(28, 24, 28, 16); ly.setSpacing(16)

        h = QHBoxLayout()
        t = QLabel("Vault Files"); t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C_TEXT};"); h.addWidget(t); h.addStretch()
        ub = self._accent_btn("\u2B06  Upload File"); ub.clicked.connect(self._upload_file)
        h.addWidget(ub); ly.addLayout(h)

        self._prog2 = QProgressBar(); self._prog2.setFixedHeight(4)
        self._prog2.setRange(0, 0); self._prog2.setStyleSheet(_PROG); self._prog2.hide()
        ly.addWidget(self._prog2)

        self._ftbl = self._mk_table(); ly.addWidget(self._ftbl, stretch=1)
        return pg

    # ── Page: Activity Log ───────────────────────────────────────────────────

    def _pg_activity(self) -> QWidget:
        pg = QWidget(); ly = QVBoxLayout(pg)
        ly.setContentsMargins(28, 24, 28, 16); ly.setSpacing(16)

        t = QLabel("Activity Log"); t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C_TEXT};"); ly.addWidget(t)

        self._ltbl = QTableWidget(); self._ltbl.setColumnCount(3)
        self._ltbl.setHorizontalHeaderLabels(["#", "Action", "Timestamp"])
        self._ltbl.horizontalHeader().setStretchLastSection(True)
        self._ltbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._ltbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._ltbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._ltbl.verticalHeader().setVisible(False)
        self._ltbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._ltbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._ltbl.setShowGrid(False); self._ltbl.setStyleSheet(_TBL)
        ly.addWidget(self._ltbl, stretch=1)
        return pg

    # ── Page: Settings ───────────────────────────────────────────────────────

    def _pg_settings(self) -> QWidget:
        pg = QWidget(); ly = QVBoxLayout(pg)
        ly.setContentsMargins(28, 24, 28, 16); ly.setSpacing(20)

        t = QLabel("Settings"); t.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C_TEXT};"); ly.addWidget(t)

        # auto-lock card
        c1 = self._card()
        c1l = QVBoxLayout(c1); c1l.setContentsMargins(24, 20, 24, 20); c1l.setSpacing(10)
        ct = QLabel("\u23F1  Auto-Lock"); ct.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        ct.setStyleSheet(f"color:{C_TEXT};border:none;"); c1l.addWidget(ct)
        ci = QLabel("The vault will automatically lock after 5 minutes of inactivity\n"
                     "to protect your files when you step away.")
        ci.setFont(QFont("Segoe UI", 12)); ci.setStyleSheet(f"color:{C_TEXT2};border:none;")
        ci.setWordWrap(True); c1l.addWidget(ci)
        ly.addWidget(c1)

        # about card
        c2 = self._card()
        c2l = QVBoxLayout(c2); c2l.setContentsMargins(24, 20, 24, 20); c2l.setSpacing(8)
        at = QLabel("\U0001F6E1\uFE0F  About Secure File Vault")
        at.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        at.setStyleSheet(f"color:{C_TEXT};border:none;"); c2l.addWidget(at)
        av = QLabel("Version 1.0.0  \u2022  Built with PyQt6, Fernet, bcrypt")
        av.setFont(QFont("Segoe UI", 12)); av.setStyleSheet(f"color:{C_TEXT2};border:none;")
        c2l.addWidget(av)

        # Google OAuth info card
        c3 = self._card()
        c3l = QVBoxLayout(c3); c3l.setContentsMargins(24, 20, 24, 20); c3l.setSpacing(8)
        gt = QLabel("\U0001F310  Google OAuth Setup")
        gt.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        gt.setStyleSheet(f"color:{C_TEXT};border:none;"); c3l.addWidget(gt)
        gi = QLabel(
            "To enable Google Sign-In, place a client_secret.json file\n"
            "from Google Cloud Console in the project root directory.\n"
            "Create Desktop-type OAuth 2.0 credentials."
        )
        gi.setFont(QFont("Segoe UI", 12)); gi.setStyleSheet(f"color:{C_TEXT2};border:none;")
        gi.setWordWrap(True); c3l.addWidget(gi)

        ly.addWidget(c2); ly.addWidget(c3); ly.addStretch()
        return pg

    # ── Reusable widgets ─────────────────────────────────────────────────────

    def _stat_card(self, title: str, value: str, icon: str, colour: str) -> QFrame:
        f = self._card(); f.setMinimumHeight(100)
        f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ly = QHBoxLayout(f); ly.setContentsMargins(20, 16, 20, 16); ly.setSpacing(14)

        badge = QLabel(icon); badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI Emoji", 20))
        badge.setStyleSheet(f"background-color:{colour}22;border-radius:12px;border:none;color:{colour};")
        ly.addWidget(badge)

        tc = QVBoxLayout(); tc.setSpacing(2)
        vl = QLabel(value); vl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        vl.setStyleSheet(f"color:{C_TEXT};border:none;"); tc.addWidget(vl)
        tl = QLabel(title); tl.setFont(QFont("Segoe UI", 11))
        tl.setStyleSheet(f"color:{C_TEXT2};border:none;"); tc.addWidget(tl)
        ly.addLayout(tc); ly.addStretch()
        return f

    def _card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background-color:{C_PANEL};border-radius:14px;border:1px solid {C_BORDER};}}")
        return f

    def _accent_btn(self, text: str) -> QPushButton:
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedHeight(38); b.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        b.setStyleSheet(
            f"QPushButton{{background-color:{C_ACCENT};color:white;border:none;"
            f"border-radius:10px;padding:0 20px;font-size:13px;}}"
            f"QPushButton:hover{{background-color:{C_ACCENT_H};}}"
        )
        return b

    def _mk_table(self) -> QTableWidget:
        t = QTableWidget(); t.setColumnCount(5)
        t.setHorizontalHeaderLabels(["File Name", "File Type", "Date Added", "SHA-256", "Actions"])
        t.horizontalHeader().setStretchLastSection(False)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        t.horizontalHeader().resizeSection(4, 230)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setShowGrid(False); t.setStyleSheet(_TBL)
        return t

    def _file_card(self, rec: dict) -> QFrame:
        f = QFrame(); f.setFixedSize(150, 140)
        f.setCursor(Qt.CursorShape.PointingHandCursor)
        f.setStyleSheet(
            f"QFrame{{background-color:{C_PANEL};border-radius:12px;"
            f"border:1px solid {C_BORDER};}}"
            f"QFrame:hover{{border:1px solid {C_ACCENT};}}"
        )
        ly = QVBoxLayout(f); ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.setContentsMargins(10, 14, 10, 10); ly.setSpacing(8)

        ext = _ext(rec["filename"])
        ic = QLabel(); ic.setPixmap(_icon_pm(ext, 48))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter); ic.setStyleSheet("border:none;")
        ly.addWidget(ic)

        nm = QLabel(rec["filename"]); nm.setFont(QFont("Segoe UI", 10))
        nm.setStyleSheet(f"color:{C_TEXT};border:none;")
        nm.setAlignment(Qt.AlignmentFlag.AlignCenter); nm.setWordWrap(True)
        nm.setMaximumWidth(130); ly.addWidget(nm)

        ft = QLabel(_ftype(rec["filename"])); ft.setFont(QFont("Segoe UI", 9))
        ft.setStyleSheet(f"color:{C_TEXT2};border:none;")
        ft.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(ft)
        return f

    # ── Navigation ───────────────────────────────────────────────────────────

    def _navigate(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_dash()
        elif idx == 1:
            self._refresh_ftbl()
        elif idx == 2:
            self._refresh_logs()

        for i, b in enumerate(self._nav_btns):
            if i == idx:
                b.setStyleSheet(_SB_BTN.format(bg=f"{C_ACCENT}20", fg=C_ACCENT, hov=f"{C_ACCENT}30"))
            else:
                b.setStyleSheet(_SB_BTN.format(bg="transparent", fg=C_TEXT2, hov="#0f172a"))

    def _on_search(self, text: str) -> None:
        self._search_text = text.strip().lower()
        i = self._stack.currentIndex()
        if i == 0:
            self._refresh_dash()
        elif i == 1:
            self._refresh_ftbl()

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _files(self) -> list[dict]:
        fl = database.get_all_files()
        if self._search_text:
            fl = [f for f in fl if self._search_text in f["filename"].lower()]
        return fl

    def _refresh_dash(self) -> None:
        fl = self._files()
        # recent grid
        while self._rc_grid.count():
            w = self._rc_grid.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        recent = fl[:8]
        for i, f in enumerate(recent):
            self._rc_grid.addWidget(self._file_card(f), i // 4, i % 4)
        if not recent:
            e = QLabel("No files in vault yet. Upload to get started.")
            e.setFont(QFont("Segoe UI", 12)); e.setStyleSheet(f"color:{C_TEXT2};")
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rc_grid.addWidget(e, 0, 0, 1, 4)
        self._fill_table(self._tbl, fl)

    def _refresh_ftbl(self) -> None:
        self._fill_table(self._ftbl, self._files())

    def _fill_table(self, tbl: QTableWidget, fl: list[dict]) -> None:
        tbl.setRowCount(len(fl))
        for row, f in enumerate(fl):
            bg = C_ROW_ALT if row % 2 else "transparent"

            # name with icon
            nw = QWidget(); nw.setStyleSheet(f"background-color:{bg};")
            nl = QHBoxLayout(nw); nl.setContentsMargins(6, 4, 6, 4); nl.setSpacing(10)
            il = QLabel(); il.setPixmap(_icon_pm(_ext(f["filename"]), 32)); il.setFixedSize(32, 32)
            nl.addWidget(il)
            nlb = QLabel(f["filename"]); nlb.setFont(QFont("Segoe UI", 12))
            nlb.setStyleSheet(f"color:{C_TEXT};"); nl.addWidget(nlb); nl.addStretch()
            tbl.setCellWidget(row, 0, nw)

            ti = QTableWidgetItem(_ftype(f["filename"])); ti.setForeground(QColor(C_TEXT2))
            tbl.setItem(row, 1, ti)

            di = QTableWidgetItem(f["date_added"]); di.setForeground(QColor(C_TEXT2))
            tbl.setItem(row, 2, di)

            hi = QTableWidgetItem(f["file_hash"][:16] + "\u2026")
            hi.setToolTip(f["file_hash"]); hi.setForeground(QColor(C_TEXT2))
            tbl.setItem(row, 3, hi)

            # actions
            aw = QWidget(); aw.setStyleSheet(f"background-color:{bg};")
            al = QHBoxLayout(aw); al.setContentsMargins(4, 4, 4, 4); al.setSpacing(8)

            vb = QPushButton("\U0001F441  View File"); vb.setCursor(Qt.CursorShape.PointingHandCursor)
            vb.setFixedHeight(30); vb.setStyleSheet(_ABTN.format(bg=C_VIEW, hov=C_VIEW_H))
            vb.clicked.connect(partial(self._view_file, f["id"]))

            db = QPushButton("\U0001F513  Decrypt"); db.setCursor(Qt.CursorShape.PointingHandCursor)
            db.setFixedHeight(30); db.setStyleSheet(_ABTN.format(bg=C_DEC, hov=C_DEC_H))
            db.clicked.connect(partial(self._decrypt_file, f["id"]))

            al.addWidget(vb); al.addWidget(db)
            tbl.setCellWidget(row, 4, aw)
        tbl.resizeRowsToContents()

    def _refresh_logs(self) -> None:
        logs = database.get_all_logs()
        self._ltbl.setRowCount(len(logs))
        for row, lg in enumerate(logs):
            ii = QTableWidgetItem(str(lg["id"])); ii.setForeground(QColor(C_TEXT2))
            self._ltbl.setItem(row, 0, ii)
            ai = QTableWidgetItem(lg["action"]); ai.setForeground(QColor(C_TEXT))
            self._ltbl.setItem(row, 1, ai)
            ti = QTableWidgetItem(lg["timestamp"]); ti.setForeground(QColor(C_TEXT2))
            self._ltbl.setItem(row, 2, ti)

    # ── File operations ──────────────────────────────────────────────────────

    def _upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file to encrypt")
        if not path:
            return
        self._show_prog(True)
        try:
            file_manager.upload_file(path, self._fernet)
            self._refresh_all()
            QMessageBox.information(self, "Success", "File encrypted and stored in vault.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Upload failed:\n{exc}")
        finally:
            self._show_prog(False)

    def _view_file(self, fid: int) -> None:
        try:
            file_manager.view_file(fid, self._fernet)
        except ValueError as exc:
            QMessageBox.warning(self, "Integrity Warning", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open file:\n{exc}")

    def _decrypt_file(self, fid: int) -> None:
        r = QMessageBox.question(
            self, "Confirm Restore",
            "This will decrypt the file back to its original location "
            "and remove it from the vault.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self._show_prog(True)
        try:
            rp = file_manager.restore_file(fid, self._fernet)
            self._refresh_all()
            QMessageBox.information(self, "Restored", f"File restored to:\n{rp}")
        except ValueError as exc:
            QMessageBox.warning(self, "Integrity Warning", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Restore failed:\n{exc}")
        finally:
            self._show_prog(False)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _show_prog(self, v: bool) -> None:
        self._prog.setVisible(v)
        self._prog2.setVisible(v)
        QApplication.processEvents()

    def _refresh_all(self) -> None:
        i = self._stack.currentIndex()
        if i == 0:
            self._refresh_dash()
        elif i == 1:
            self._refresh_ftbl()

    # ── Logout ───────────────────────────────────────────────────────────────

    def _logout(self) -> None:
        file_manager.cleanup_temp_files()
        database.add_log("User logged out")
        self.logout_requested.emit()

    # ── Auto-lock ────────────────────────────────────────────────────────────

    def _setup_auto_lock(self) -> None:
        self._ltmr = QTimer(self)
        self._ltmr.setInterval(AUTO_LOCK_MS)
        self._ltmr.setSingleShot(True)
        self._ltmr.timeout.connect(self._auto_lock)
        self._ltmr.start()
        self.installEventFilter(self)

    def eventFilter(self, obj, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() in (
            QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress, QEvent.Type.Wheel,
        ):
            self._ltmr.start()
        return super().eventFilter(obj, event)

    def _auto_lock(self) -> None:
        database.add_log("Auto-lock triggered (inactivity)")
        self.logout_requested.emit()
