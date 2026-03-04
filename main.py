"""
main.py - Entry point for Secure File Vault.

Initialises the database, creates the QApplication, and manages transitions
between the login screen and the main dashboard.
"""

import sys
import os

# Ensure the project root is on the module search path so that imports like
# ``import database`` work regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

import database
import auth_service
from ui.login_window import LoginWindow
from ui.dashboard import Dashboard


class MainWindow(QMainWindow):
    """Top-level window that switches between Login and Dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Secure File Vault")
        self.resize(1100, 700)
        self.setMinimumSize(900, 550)

        # Central stacked widget
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Login screen (always at index 0)
        self._login = LoginWindow()
        self._login.authenticated.connect(self._on_authenticated)
        self._stack.addWidget(self._login)

        # Dashboard placeholder – created after login
        self._dashboard: Dashboard | None = None

        self._apply_global_style()

    def _apply_global_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0f172a;
            }
            QToolTip {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                padding: 4px;
                font-size: 12px;
            }
            """
        )

    # ── Slot: successful authentication ──────────────────────────────────────

    def _on_authenticated(self, password: str, salt: bytes) -> None:
        # Remove old dashboard if any
        if self._dashboard is not None:
            self._stack.removeWidget(self._dashboard)
            self._dashboard.deleteLater()

        self._dashboard = Dashboard(password, salt)
        self._dashboard.logout_requested.connect(self._on_logout)
        self._stack.addWidget(self._dashboard)
        self._stack.setCurrentWidget(self._dashboard)

    # ── Slot: logout / auto-lock ─────────────────────────────────────────────

    def _on_logout(self) -> None:
        auth_service.clear_session()
        self._login.reset()
        self._stack.setCurrentWidget(self._login)

        if self._dashboard is not None:
            self._stack.removeWidget(self._dashboard)
            self._dashboard.deleteLater()
            self._dashboard = None


def main() -> None:
    # Initialise the database (creates tables on first run)
    database.initialize_database()

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
