"""
ui/login_window.py - Multi-step login / registration / recovery screen.

Pages (QStackedWidget indices):
  0 – Account authentication (email/password + Google OAuth)
  1 – Vault master password
  2 – Forgot Password  (enter email → send reset token)
  3 – Reset Password   (enter token + new password)
  4 – Forgot Master PIN (enter email → send OTP)
  5 – OTP Verification  (enter 6-digit code)
  6 – Master PIN Reset   (enter new PIN)

After successful login + vault unlock the ``authenticated`` signal is emitted
with (vault_password, salt_bytes).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QStackedWidget,
    QSizePolicy,
)

import auth
import auth_service
import recovery_service

# ── Colour tokens ────────────────────────────────────────────────────────────

C_BG      = "#0f172a"
C_PANEL   = "#1e293b"
C_ACCENT  = "#6366f1"
C_ACC_H   = "#818cf8"
C_TEXT    = "#e2e8f0"
C_TEXT2   = "#94a3b8"
C_BORDER  = "#334155"
C_DANGER  = "#ef4444"
C_SUCCESS = "#22c55e"
C_GOOGLE  = "#4285F4"
C_GOOGH   = "#5a9bf4"

# ── Re-usable stylesheets ───────────────────────────────────────────────────

_INPUT = f"""
QLineEdit {{
    background-color: #0f172a;
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0 14px;
    font-size: 14px;
    font-family: 'Segoe UI';
}}
QLineEdit:focus {{
    border: 1px solid {C_ACCENT};
}}
"""

_PRIMARY_BTN = f"""
QPushButton {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI';
}}
QPushButton:hover {{
    background-color: {C_ACC_H};
}}
QPushButton:pressed {{
    background-color: #4f46e5;
}}
QPushButton:disabled {{
    background-color: #334155;
    color: #64748b;
}}
"""

_GOOGLE_BTN = f"""
QPushButton {{
    background-color: {C_GOOGLE};
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI';
}}
QPushButton:hover {{
    background-color: {C_GOOGH};
}}
QPushButton:disabled {{
    background-color: #334155;
    color: #64748b;
}}
"""

_LINK_BTN = f"""
QPushButton {{
    background: none;
    border: none;
    color: {C_ACCENT};
    font-size: 12px;
    font-family: 'Segoe UI';
    text-decoration: underline;
}}
QPushButton:hover {{
    color: {C_ACC_H};
}}
"""

_SECONDARY_BTN = f"""
QPushButton {{
    background-color: transparent;
    color: {C_ACCENT};
    border: 1px solid {C_ACCENT};
    border-radius: 10px;
    font-size: 13px;
    font-family: 'Segoe UI';
}}
QPushButton:hover {{
    background-color: {C_ACCENT};
    color: white;
}}
QPushButton:disabled {{
    border-color: #334155;
    color: #64748b;
}}
"""


# ── Helper: build a styled card ─────────────────────────────────────────────

def _card(width: int = 440, height: int = 560) -> tuple[QWidget, QFrame, QVBoxLayout]:
    """Return (wrapper, card_frame, card_layout) for a centred card page."""
    wrapper = QWidget()
    wl = QVBoxLayout(wrapper)
    wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card = QFrame()
    card.setFixedSize(width, height)
    card.setStyleSheet(
        f"QFrame {{ background-color: {C_PANEL}; border-radius: 18px;"
        f" border: 1px solid {C_BORDER}; }}"
    )
    cl = QVBoxLayout(card)
    cl.setAlignment(Qt.AlignmentFlag.AlignTop)
    cl.setSpacing(14)
    cl.setContentsMargins(36, 32, 36, 28)
    wl.addWidget(card)
    return wrapper, card, cl


def _label(text: str, size: int = 11, color: str = C_TEXT2, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    lbl.setFont(QFont("Segoe UI", size, w))
    lbl.setStyleSheet(f"color: {color}; border: none;")
    return lbl


def _input(placeholder: str, echo: bool = False, height: int = 42) -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setFixedHeight(height)
    le.setStyleSheet(_INPUT)
    if echo:
        le.setEchoMode(QLineEdit.EchoMode.Password)
    return le


def _btn(text: str, stylesheet: str = _PRIMARY_BTN, height: int = 44) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFixedHeight(height)
    b.setStyleSheet(stylesheet)
    return b


def _error_label() -> QLabel:
    lbl = QLabel("")
    lbl.setStyleSheet(f"color: {C_DANGER}; font-size: 12px; border: none;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _success_label() -> QLabel:
    lbl = QLabel("")
    lbl.setStyleSheet(f"color: {C_SUCCESS}; font-size: 12px; border: none;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _back_btn(text: str = "\u2190  Back to sign in") -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(_LINK_BTN)
    return b


# ── Google OAuth worker thread ───────────────────────────────────────────────

class _GoogleWorker(QThread):
    success = pyqtSignal(str)   # access_token
    error   = pyqtSignal(str)

    def run(self) -> None:
        ok, access_token, _, err = auth_service.run_google_oauth()
        if ok:
            self.success.emit(access_token)
        else:
            self.error.emit(err)


class _ApiWorker(QThread):
    """Run an arbitrary callable off the UI thread and emit its return value."""

    finished = pyqtSignal(object)   # result tuple from the wrapped function

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self._fn = fn
        self._args = args

    def run(self) -> None:
        try:
            result = self._fn(*self._args)
        except Exception as exc:
            result = (False, str(exc))
        self.finished.emit(result)


# ═════════════════════════════════════════════════════════════════════════════
#  LoginWindow
# ═════════════════════════════════════════════════════════════════════════════

class LoginWindow(QWidget):
    """Multi-page login / recovery widget."""

    authenticated = pyqtSignal(str, bytes)   # (vault_password, salt)

    # Page indices
    PAGE_AUTH       = 0
    PAGE_VAULT      = 1
    PAGE_FORGOT_PW  = 2
    PAGE_RESET_PW   = 3
    PAGE_FORGOT_PIN = 4
    PAGE_OTP_VERIFY = 5
    PAGE_PIN_RESET  = 6

    def __init__(self) -> None:
        super().__init__()
        self._mode = "signin"
        self._google_worker: _GoogleWorker | None = None
        self._pending_password: str | None = None
        self._recovery_email: str = ""
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setInterval(1000)
        self._cooldown_timer.timeout.connect(self._tick_cooldown)
        self._cooldown_remaining = 0
        self._active_resend_btn: QPushButton | None = None
        self._active_resend_label: QLabel | None = None
        self._api_workers: list[_ApiWorker] = []   # prevent GC of in-flight workers
        self._init_ui()

    # ─────────────────────────────────────────────────────────────────────────
    #  UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        self.setStyleSheet(f"background-color: {C_BG};")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._pages = QStackedWidget()
        self._pages.setStyleSheet(f"background-color: {C_BG};")
        self._pages.addWidget(self._build_auth_page())        # 0
        self._pages.addWidget(self._build_vault_page())       # 1
        self._pages.addWidget(self._build_forgot_pw_page())   # 2
        self._pages.addWidget(self._build_reset_pw_page())    # 3
        self._pages.addWidget(self._build_forgot_pin_page())  # 4
        self._pages.addWidget(self._build_otp_verify_page())  # 5
        self._pages.addWidget(self._build_pin_reset_page())   # 6
        outer.addWidget(self._pages)

    # ── Page 0: Account auth ─────────────────────────────────────────────────

    def _build_auth_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 590)

        # title
        t = _label("Secure File Vault", 22, C_ACCENT, bold=True)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(t)

        ic = QLabel("\U0001F6E1\uFE0F")
        ic.setFont(QFont("Segoe UI Emoji", 36))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("color: white; border: none;")
        cl.addWidget(ic)

        self._auth_subtitle = _label("Sign in to your account", 11, C_TEXT2)
        self._auth_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self._auth_subtitle)
        cl.addSpacing(4)

        cl.addWidget(_label("Email"))
        self._email = _input("you@example.com")
        cl.addWidget(self._email)

        cl.addWidget(_label("Password"))
        self._password = _input("Enter password\u2026", echo=True)
        self._password.returnPressed.connect(self._on_auth_submit)
        cl.addWidget(self._password)

        self._confirm_label = _label("Confirm Password")
        self._confirm_label.setVisible(False)
        cl.addWidget(self._confirm_label)
        self._confirm = _input("Re-enter password\u2026", echo=True)
        self._confirm.setVisible(False)
        self._confirm.returnPressed.connect(self._on_auth_submit)
        cl.addWidget(self._confirm)

        self._auth_btn = _btn("Sign In")
        self._auth_btn.clicked.connect(self._on_auth_submit)
        cl.addWidget(self._auth_btn)

        # Forgot links row
        links_row = QHBoxLayout()
        self._forgot_pw_link = QPushButton("Forgot Password?")
        self._forgot_pw_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._forgot_pw_link.setStyleSheet(_LINK_BTN)
        self._forgot_pw_link.clicked.connect(
            lambda: self._pages.setCurrentIndex(self.PAGE_FORGOT_PW)
        )
        links_row.addWidget(self._forgot_pw_link)
        links_row.addStretch()
        self._forgot_pin_link = QPushButton("Forgot Master PIN?")
        self._forgot_pin_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._forgot_pin_link.setStyleSheet(_LINK_BTN)
        self._forgot_pin_link.clicked.connect(
            lambda: self._pages.setCurrentIndex(self.PAGE_FORGOT_PIN)
        )
        links_row.addWidget(self._forgot_pin_link)
        cl.addLayout(links_row)

        # toggle
        self._toggle_btn = QPushButton("Don\u2019t have an account? Register")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(_LINK_BTN)
        self._toggle_btn.clicked.connect(self._toggle_mode)
        cl.addWidget(self._toggle_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # divider
        div_row = QHBoxLayout()
        for i in range(2):
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(
                f"color: {C_BORDER}; border: none; background-color: {C_BORDER};"
            )
            line.setFixedHeight(1)
            div_row.addWidget(line)
            if i == 0:
                or_lbl = _label("OR", 10, C_TEXT2, bold=True)
                or_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                or_lbl.setFixedWidth(40)
                div_row.addWidget(or_lbl)
        cl.addLayout(div_row)

        # Google
        self._google_btn = _btn("\U0001F310  Sign in with Google", _GOOGLE_BTN)
        self._google_btn.clicked.connect(self._on_google)
        cl.addWidget(self._google_btn)

        # error
        self._auth_error = _error_label()
        cl.addWidget(self._auth_error)

        return wrapper

    # ── Page 1: Vault master password ────────────────────────────────────────

    def _build_vault_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 420)

        self._vault_title = _label("Unlock Vault", 20, C_ACCENT, bold=True)
        self._vault_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self._vault_title)

        ic = QLabel("\U0001F510")
        ic.setFont(QFont("Segoe UI Emoji", 36))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        self._vault_info = _label(
            "Your files are encrypted with a separate vault password.", 11, C_TEXT2
        )
        self._vault_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vault_info.setWordWrap(True)
        cl.addWidget(self._vault_info)
        cl.addSpacing(4)

        cl.addWidget(_label("Vault Password"))
        self._vault_pw = _input("Vault master password\u2026", echo=True)
        self._vault_pw.returnPressed.connect(self._on_vault_submit)
        cl.addWidget(self._vault_pw)

        self._vault_confirm_label = _label("Confirm Vault Password")
        self._vault_confirm_label.setVisible(False)
        cl.addWidget(self._vault_confirm_label)
        self._vault_confirm = _input("Re-enter vault password\u2026", echo=True)
        self._vault_confirm.setVisible(False)
        self._vault_confirm.returnPressed.connect(self._on_vault_submit)
        cl.addWidget(self._vault_confirm)

        self._vault_btn = _btn("Unlock Vault")
        self._vault_btn.clicked.connect(self._on_vault_submit)
        cl.addWidget(self._vault_btn)

        self._vault_error = _error_label()
        cl.addWidget(self._vault_error)

        back = _back_btn()
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_AUTH))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ── Page 2: Forgot Password ──────────────────────────────────────────────

    def _build_forgot_pw_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 400)

        _fp_title = _label("Forgot Password", 20, C_ACCENT, bold=True)
        _fp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_fp_title)

        ic = QLabel("\U0001F4E7")
        ic.setFont(QFont("Segoe UI Emoji", 32))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        info = _label("Enter your registered email to receive a reset token.", 11, C_TEXT2)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        cl.addWidget(info)
        cl.addSpacing(4)

        cl.addWidget(_label("Email"))
        self._fp_email = _input("you@example.com")
        self._fp_email.returnPressed.connect(self._on_forgot_pw_submit)
        cl.addWidget(self._fp_email)

        self._fp_send_btn = _btn("Send Reset Email")
        self._fp_send_btn.clicked.connect(self._on_forgot_pw_submit)
        cl.addWidget(self._fp_send_btn)

        # resend row
        resend_row = QHBoxLayout()
        self._fp_resend_btn = _btn("Resend Reset Email", _SECONDARY_BTN, 36)
        self._fp_resend_btn.setVisible(False)
        self._fp_resend_btn.clicked.connect(self._on_resend_reset_email)
        resend_row.addWidget(self._fp_resend_btn)
        self._fp_resend_label = _label("", 11, C_TEXT2)
        self._fp_resend_label.setVisible(False)
        resend_row.addWidget(self._fp_resend_label)
        cl.addLayout(resend_row)

        self._fp_success = _success_label()
        cl.addWidget(self._fp_success)
        self._fp_error = _error_label()
        cl.addWidget(self._fp_error)

        # link to enter token
        self._fp_have_token = QPushButton("I already have a token")
        self._fp_have_token.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fp_have_token.setStyleSheet(_LINK_BTN)
        self._fp_have_token.clicked.connect(
            lambda: self._pages.setCurrentIndex(self.PAGE_RESET_PW)
        )
        cl.addWidget(self._fp_have_token, alignment=Qt.AlignmentFlag.AlignCenter)

        back = _back_btn()
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_AUTH))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ── Page 3: Reset Password ───────────────────────────────────────────────

    def _build_reset_pw_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 480)

        _rp_title = _label("Reset Password", 20, C_ACCENT, bold=True)
        _rp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_rp_title)

        ic = QLabel("\U0001F512")
        ic.setFont(QFont("Segoe UI Emoji", 32))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        info = _label("Enter the token from your email and set a new password.", 11, C_TEXT2)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        cl.addWidget(info)
        cl.addSpacing(4)

        cl.addWidget(_label("Reset Token"))
        self._rp_token = _input("Paste your reset token\u2026")
        cl.addWidget(self._rp_token)

        cl.addWidget(_label("New Password"))
        self._rp_new_pw = _input("Enter new password\u2026", echo=True)
        cl.addWidget(self._rp_new_pw)

        cl.addWidget(_label("Confirm Password"))
        self._rp_confirm = _input("Re-enter new password\u2026", echo=True)
        self._rp_confirm.returnPressed.connect(self._on_reset_pw_submit)
        cl.addWidget(self._rp_confirm)

        self._rp_btn = _btn("Reset Password")
        self._rp_btn.clicked.connect(self._on_reset_pw_submit)
        cl.addWidget(self._rp_btn)

        self._rp_success = _success_label()
        cl.addWidget(self._rp_success)
        self._rp_error = _error_label()
        cl.addWidget(self._rp_error)

        back = _back_btn()
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_AUTH))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ── Page 4: Forgot Master PIN ────────────────────────────────────────────

    def _build_forgot_pin_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 400)

        _fpin_title = _label("Forgot Master PIN", 20, C_ACCENT, bold=True)
        _fpin_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_fpin_title)

        ic = QLabel("\U0001F511")
        ic.setFont(QFont("Segoe UI Emoji", 32))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        info = _label(
            "Enter your registered email. We\u2019ll send a 6-digit OTP to verify your identity.",
            11, C_TEXT2,
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        cl.addWidget(info)
        cl.addSpacing(4)

        cl.addWidget(_label("Email"))
        self._fpin_email = _input("you@example.com")
        self._fpin_email.returnPressed.connect(self._on_forgot_pin_submit)
        cl.addWidget(self._fpin_email)

        self._fpin_send_btn = _btn("Send OTP")
        self._fpin_send_btn.clicked.connect(self._on_forgot_pin_submit)
        cl.addWidget(self._fpin_send_btn)

        self._fpin_success = _success_label()
        cl.addWidget(self._fpin_success)
        self._fpin_error = _error_label()
        cl.addWidget(self._fpin_error)

        back = _back_btn()
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_AUTH))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ── Page 5: OTP Verification ─────────────────────────────────────────────

    def _build_otp_verify_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 440)

        _otp_title = _label("Verify OTP", 20, C_ACCENT, bold=True)
        _otp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_otp_title)

        ic = QLabel("\U0001F4F2")
        ic.setFont(QFont("Segoe UI Emoji", 32))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        self._otp_email_label = _label("Enter the code sent to your email", 11, C_TEXT2)
        self._otp_email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._otp_email_label.setWordWrap(True)
        cl.addWidget(self._otp_email_label)
        cl.addSpacing(8)

        # OTP input – single wide field with letter-spacing
        self._otp_input = QLineEdit()
        self._otp_input.setPlaceholderText("\u2022 \u2022 \u2022 \u2022 \u2022 \u2022")
        self._otp_input.setMaxLength(6)
        self._otp_input.setFixedHeight(54)
        self._otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._otp_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: #0f172a;
                color: {C_ACCENT};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
                font-size: 26px;
                font-family: 'Consolas', 'Courier New', monospace;
                letter-spacing: 12px;
                padding: 0 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C_ACCENT};
            }}
            """
        )
        self._otp_input.returnPressed.connect(self._on_otp_verify)
        cl.addWidget(self._otp_input)
        cl.addSpacing(4)

        self._otp_verify_btn = _btn("Verify")
        self._otp_verify_btn.clicked.connect(self._on_otp_verify)
        cl.addWidget(self._otp_verify_btn)

        # "Didn't receive?" + resend
        _no_code_lbl = _label("Didn\u2019t receive the code?", 11, C_TEXT2)
        _no_code_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_no_code_lbl)

        resend_row = QHBoxLayout()
        resend_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._otp_resend_btn = _btn("Resend OTP", _SECONDARY_BTN, 36)
        self._otp_resend_btn.clicked.connect(self._on_resend_otp)
        resend_row.addWidget(self._otp_resend_btn)
        self._otp_resend_label = _label("", 11, C_TEXT2)
        resend_row.addWidget(self._otp_resend_label)
        cl.addLayout(resend_row)

        self._otp_success = _success_label()
        cl.addWidget(self._otp_success)
        self._otp_error = _error_label()
        cl.addWidget(self._otp_error)

        back = _back_btn("\u2190  Back")
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_FORGOT_PIN))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ── Page 6: Master PIN Reset ─────────────────────────────────────────────

    def _build_pin_reset_page(self) -> QWidget:
        wrapper, card, cl = _card(440, 420)

        _pin_title = _label("Reset Master PIN", 20, C_ACCENT, bold=True)
        _pin_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(_pin_title)

        ic = QLabel("\U0001F510")
        ic.setFont(QFont("Segoe UI Emoji", 32))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("border: none;")
        cl.addWidget(ic)

        info = _label("Set a new Master PIN for your vault.", 11, C_TEXT2)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        cl.addWidget(info)
        cl.addSpacing(4)

        cl.addWidget(_label("New Master PIN"))
        self._pr_new_pin = _input("Enter new Master PIN\u2026", echo=True)
        cl.addWidget(self._pr_new_pin)

        cl.addWidget(_label("Confirm Master PIN"))
        self._pr_confirm = _input("Re-enter Master PIN\u2026", echo=True)
        self._pr_confirm.returnPressed.connect(self._on_pin_reset_submit)
        cl.addWidget(self._pr_confirm)

        self._pr_btn = _btn("Reset Master PIN")
        self._pr_btn.clicked.connect(self._on_pin_reset_submit)
        cl.addWidget(self._pr_btn)

        self._pr_success = _success_label()
        cl.addWidget(self._pr_success)
        self._pr_error = _error_label()
        cl.addWidget(self._pr_error)

        back = _back_btn()
        back.clicked.connect(lambda: self._pages.setCurrentIndex(self.PAGE_AUTH))
        cl.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        return wrapper

    # ─────────────────────────────────────────────────────────────────────────
    #  AUTH LOGIC (Page 0)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Background-API helper ─────────────────────────────────────────────

    def _run_api(self, fn, args: tuple, callback) -> None:
        """Run *fn(*args)* on a background thread; invoke *callback(result)* on the UI thread."""
        worker = _ApiWorker(fn, *args)
        self._api_workers.append(worker)
        worker.finished.connect(callback)
        worker.finished.connect(lambda: (
            self._api_workers.remove(worker) if worker in self._api_workers else None
        ))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _toggle_mode(self) -> None:
        if self._mode == "signin":
            self._mode = "register"
            self._auth_subtitle.setText("Create a new account")
            self._auth_btn.setText("Register")
            self._toggle_btn.setText("Already have an account? Sign In")
            self._confirm_label.setVisible(True)
            self._confirm.setVisible(True)
        else:
            self._mode = "signin"
            self._auth_subtitle.setText("Sign in to your account")
            self._auth_btn.setText("Sign In")
            self._toggle_btn.setText("Don\u2019t have an account? Register")
            self._confirm_label.setVisible(False)
            self._confirm.setVisible(False)
        self._auth_error.setText("")

    def _on_auth_submit(self) -> None:
        email = self._email.text().strip()
        password = self._password.text().strip()
        if not email or not password:
            self._auth_error.setText("Email and password are required.")
            return
        if self._mode == "register":
            confirm = self._confirm.text().strip()
            if password != confirm:
                self._auth_error.setText("Passwords do not match.")
                return
            fn = auth_service.register
        else:
            fn = auth_service.login

        self._auth_btn.setEnabled(False)
        self._auth_btn.setText("Please wait\u2026")
        self._auth_error.setText("")

        def _on_result(result):
            self._auth_btn.setEnabled(True)
            self._auth_btn.setText("Register" if self._mode == "register" else "Sign In")
            ok, msg = result
            if not ok:
                self._auth_error.setText(msg)
                return
            self._auth_error.setText("")
            self._pending_password = password
            self._try_auto_vault(password)

        self._run_api(fn, (email, password), _on_result)

    # ── Google OAuth ─────────────────────────────────────────────────────────

    def _on_google(self) -> None:
        if not auth_service.google_oauth_available():
            self._auth_error.setText(
                "Google OAuth not configured.\n"
                "Place client_secret.json in the project folder."
            )
            return
        self._google_btn.setEnabled(False)
        self._google_btn.setText("Waiting for Google\u2026")
        self._auth_error.setText("")
        self._google_worker = _GoogleWorker()
        self._google_worker.success.connect(self._on_google_ok)
        self._google_worker.error.connect(self._on_google_err)
        self._google_worker.start()

    def _on_google_ok(self, access_token: str) -> None:
        self._google_btn.setText("Verifying\u2026")
        self._auth_error.setText("")

        def _on_result(result):
            self._google_btn.setEnabled(True)
            self._google_btn.setText("\U0001F310  Sign in with Google")
            ok, msg = result
            if not ok:
                self._auth_error.setText(msg)
                return
            self._pending_password = None
            self._show_vault_page()

        self._run_api(auth_service.complete_google_login, (access_token,), _on_result)

    def _on_google_err(self, err: str) -> None:
        self._google_btn.setEnabled(True)
        self._google_btn.setText("\U0001F310  Sign in with Google")
        self._auth_error.setText(f"Google sign-in failed:\n{err}")

    # ── Vault password (Page 1) ──────────────────────────────────────────────

    def _try_auto_vault(self, password: str) -> None:
        if auth.is_first_launch():
            salt = auth.register_user(password)
            self.authenticated.emit(password, salt)
            return
        ok, salt = auth.login(password)
        if ok and salt is not None:
            self.authenticated.emit(password, salt)
            return
        self._show_vault_page()

    def _show_vault_page(self) -> None:
        creating = auth.is_first_launch()
        if creating:
            self._vault_title.setText("Create Vault Password")
            self._vault_btn.setText("Create Vault")
            self._vault_info.setText(
                "Set a master password to encrypt your files.\n"
                "This can differ from your account password."
            )
            self._vault_confirm_label.setVisible(True)
            self._vault_confirm.setVisible(True)
        else:
            self._vault_title.setText("Unlock Vault")
            self._vault_btn.setText("Unlock Vault")
            self._vault_info.setText(
                "Enter your vault master password to decrypt files."
            )
            self._vault_confirm_label.setVisible(False)
            self._vault_confirm.setVisible(False)
        self._vault_pw.clear()
        self._vault_confirm.clear()
        self._vault_error.setText("")
        self._pages.setCurrentIndex(self.PAGE_VAULT)

    def _on_vault_submit(self) -> None:
        pw = self._vault_pw.text().strip()
        if not pw:
            self._vault_error.setText("Password cannot be empty.")
            return
        if auth.is_first_launch():
            confirm = self._vault_confirm.text().strip()
            if pw != confirm:
                self._vault_error.setText("Passwords do not match.")
                return
            if len(pw) < 6:
                self._vault_error.setText("Must be at least 6 characters.")
                return
            salt = auth.register_user(pw)
            self.authenticated.emit(pw, salt)
        else:
            ok, salt = auth.login(pw)
            if ok and salt is not None:
                self.authenticated.emit(pw, salt)
            else:
                self._vault_error.setText("Incorrect vault password.")

    # ─────────────────────────────────────────────────────────────────────────
    #  FORGOT PASSWORD (Pages 2-3)
    # ─────────────────────────────────────────────────────────────────────────

    def _on_forgot_pw_submit(self) -> None:
        email = self._fp_email.text().strip()
        if not email:
            self._fp_error.setText("Please enter your email.")
            return
        self._fp_error.setText("")
        self._fp_success.setText("")
        self._fp_send_btn.setEnabled(False)
        self._fp_send_btn.setText("Sending\u2026")

        def _on_result(result):
            self._fp_send_btn.setEnabled(True)
            self._fp_send_btn.setText("Send Reset Email")
            ok, msg = result
            if not ok:
                self._fp_error.setText(msg)
                return
            self._recovery_email = email
            self._fp_success.setText(msg)
            self._fp_resend_btn.setVisible(True)
            self._fp_resend_label.setVisible(True)
            self._start_cooldown(self._fp_resend_btn, self._fp_resend_label)

        self._run_api(recovery_service.request_password_reset, (email,), _on_result)

    def _on_resend_reset_email(self) -> None:
        email = self._fp_email.text().strip() or self._recovery_email
        if not email:
            self._fp_error.setText("Please enter your email.")
            return
        self._fp_error.setText("")
        self._fp_success.setText("")
        self._fp_resend_btn.setEnabled(False)

        def _on_result(result):
            self._fp_resend_btn.setEnabled(True)
            ok, msg = result
            if not ok:
                self._fp_error.setText(msg)
                return
            self._fp_success.setText(msg)
            self._start_cooldown(self._fp_resend_btn, self._fp_resend_label)

        self._run_api(recovery_service.resend_password_reset, (email,), _on_result)

    def _on_reset_pw_submit(self) -> None:
        token = self._rp_token.text().strip()
        new_pw = self._rp_new_pw.text().strip()
        confirm = self._rp_confirm.text().strip()

        if not token:
            self._rp_error.setText("Please enter the reset token.")
            return
        if not new_pw:
            self._rp_error.setText("Please enter a new password.")
            return
        if new_pw != confirm:
            self._rp_error.setText("Passwords do not match.")
            return

        self._rp_error.setText("")
        self._rp_success.setText("")
        self._rp_btn.setEnabled(False)
        self._rp_btn.setText("Resetting\u2026")

        def _on_result(result):
            self._rp_btn.setEnabled(True)
            self._rp_btn.setText("Reset Password")
            ok, msg = result
            if not ok:
                self._rp_error.setText(msg)
                return
            self._rp_success.setText(msg)
            self._rp_token.clear()
            self._rp_new_pw.clear()
            self._rp_confirm.clear()
            # Invalidate session – user must re-login
            auth_service.clear_session()

        self._run_api(recovery_service.reset_password, (token, new_pw), _on_result)

    # ─────────────────────────────────────────────────────────────────────────
    #  FORGOT MASTER PIN (Pages 4-6)
    # ─────────────────────────────────────────────────────────────────────────

    def _on_forgot_pin_submit(self) -> None:
        email = self._fpin_email.text().strip()
        if not email:
            self._fpin_error.setText("Please enter your email.")
            return
        self._fpin_error.setText("")
        self._fpin_success.setText("")
        self._fpin_send_btn.setEnabled(False)
        self._fpin_send_btn.setText("Sending\u2026")

        def _on_result(result):
            self._fpin_send_btn.setEnabled(True)
            self._fpin_send_btn.setText("Send OTP")
            ok, msg = result
            if not ok:
                self._fpin_error.setText(msg)
                return
            self._recovery_email = email
            self._fpin_success.setText(msg)
            # Navigate to OTP page
            self._otp_email_label.setText(f"Enter the code sent to {email}")
            self._otp_input.clear()
            self._otp_error.setText("")
            self._otp_success.setText("")
            self._pages.setCurrentIndex(self.PAGE_OTP_VERIFY)

        self._run_api(recovery_service.request_master_pin_otp, (email,), _on_result)

    def _on_otp_verify(self) -> None:
        otp = self._otp_input.text().strip()
        if not otp or len(otp) != 6:
            self._otp_error.setText("Please enter the 6-digit code.")
            return

        self._otp_error.setText("")
        self._otp_success.setText("")
        self._otp_verify_btn.setEnabled(False)
        self._otp_verify_btn.setText("Verifying\u2026")

        def _on_result(result):
            self._otp_verify_btn.setEnabled(True)
            self._otp_verify_btn.setText("Verify")
            ok, msg = result
            if not ok:
                self._otp_error.setText(msg)
                return
            self._otp_success.setText(msg)
            # Navigate to PIN reset page
            self._pr_new_pin.clear()
            self._pr_confirm.clear()
            self._pr_error.setText("")
            self._pr_success.setText("")
            self._pages.setCurrentIndex(self.PAGE_PIN_RESET)

        self._run_api(recovery_service.verify_otp, (self._recovery_email, otp), _on_result)

    def _on_resend_otp(self) -> None:
        if not self._recovery_email:
            self._otp_error.setText("No email set. Go back and try again.")
            return
        self._otp_error.setText("")
        self._otp_success.setText("")
        self._otp_resend_btn.setEnabled(False)

        def _on_result(result):
            self._otp_resend_btn.setEnabled(True)
            ok, msg = result
            if not ok:
                self._otp_error.setText(msg)
                return
            self._otp_success.setText(msg)
            self._otp_input.clear()
            self._start_cooldown(self._otp_resend_btn, self._otp_resend_label)

        self._run_api(recovery_service.resend_otp, (self._recovery_email,), _on_result)

    def _on_pin_reset_submit(self) -> None:
        new_pin = self._pr_new_pin.text().strip()
        confirm = self._pr_confirm.text().strip()

        if not new_pin:
            self._pr_error.setText("Please enter a new Master PIN.")
            return
        if new_pin != confirm:
            self._pr_error.setText("PINs do not match.")
            return

        self._pr_error.setText("")
        self._pr_success.setText("")
        self._pr_btn.setEnabled(False)
        self._pr_btn.setText("Resetting\u2026")

        def _on_result(result):
            self._pr_btn.setEnabled(True)
            self._pr_btn.setText("Reset Master PIN")
            ok, msg = result
            if not ok:
                self._pr_error.setText(msg)
                return
            self._pr_success.setText(msg)
            self._pr_new_pin.clear()
            self._pr_confirm.clear()
            # Invalidate session – user must re-login
            auth_service.clear_session()

        self._run_api(recovery_service.reset_master_pin, (self._recovery_email, new_pin), _on_result)

    # ─────────────────────────────────────────────────────────────────────────
    #  COOLDOWN TIMER
    # ─────────────────────────────────────────────────────────────────────────

    def _start_cooldown(self, btn: QPushButton, label: QLabel) -> None:
        """Disable *btn* for RESEND_COOLDOWN_SECONDS and show countdown in *label*."""
        self._cooldown_remaining = recovery_service.RESEND_COOLDOWN_SECONDS
        self._active_resend_btn = btn
        self._active_resend_label = label
        btn.setEnabled(False)
        label.setText(f"Resend available in {self._cooldown_remaining}s")
        label.setVisible(True)
        self._cooldown_timer.start()

    def _tick_cooldown(self) -> None:
        self._cooldown_remaining -= 1
        if self._cooldown_remaining <= 0:
            self._cooldown_timer.stop()
            if self._active_resend_btn:
                self._active_resend_btn.setEnabled(True)
            if self._active_resend_label:
                self._active_resend_label.setText("")
                self._active_resend_label.setVisible(False)
            return
        if self._active_resend_label:
            self._active_resend_label.setText(
                f"Resend available in {self._cooldown_remaining}s"
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  RESET
    # ─────────────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all fields and return to the sign-in page."""
        auth_service.clear_session()
        self._cooldown_timer.stop()

        # Auth page
        self._email.clear()
        self._password.clear()
        self._confirm.clear()
        self._auth_error.setText("")
        self._pending_password = None

        # Vault page
        self._vault_pw.clear()
        self._vault_confirm.clear()
        self._vault_error.setText("")

        # Forgot password page
        self._fp_email.clear()
        self._fp_error.setText("")
        self._fp_success.setText("")
        self._fp_resend_btn.setVisible(False)
        self._fp_resend_label.setVisible(False)

        # Reset password page
        self._rp_token.clear()
        self._rp_new_pw.clear()
        self._rp_confirm.clear()
        self._rp_error.setText("")
        self._rp_success.setText("")

        # Forgot PIN page
        self._fpin_email.clear()
        self._fpin_error.setText("")
        self._fpin_success.setText("")

        # OTP page
        self._otp_input.clear()
        self._otp_error.setText("")
        self._otp_success.setText("")

        # PIN reset page
        self._pr_new_pin.clear()
        self._pr_confirm.clear()
        self._pr_error.setText("")
        self._pr_success.setText("")

        self._recovery_email = ""
        self._pages.setCurrentIndex(self.PAGE_AUTH)

        if self._mode == "register":
            self._toggle_mode()
