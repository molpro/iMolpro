import os
import pathlib
from typing import Optional

from PyQt5.QtWidgets import (
    QTextBrowser, QMainWindow, QShortcut, QWidget, QHBoxLayout, QDialog, QVBoxLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QKeySequence
from MenuBar import MenuBar


class HelpWindow(QWidget):
    """
    A window displaying help text or documentation files.
    """

    def __init__(self, text: Optional[str] = None):
        super().__init__()
        self._init_ui(text)

    def _init_ui(self, text: Optional[str]):
        layout = QHBoxLayout(self)
        self.setLayout(layout)
        self.browser = QTextBrowser()
        layout.addWidget(self.browser)
        if text:
            self.browser.setText(text)
        self.browser.setOpenExternalLinks(True)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(650)
        self.setMinimumHeight(400)
        self.shortcutClose = QShortcut(QKeySequence('Ctrl+W'), self)
        self.shortcutClose.activated.connect(self.close)

    def setSource(self, file: QUrl):
        self.browser.setSource(file)


class HelpManager:
    """
    Manages help/documentation actions in the application.
    """

    def __init__(self, menubar: MenuBar):
        self.menubar = menubar

    def register(self, name: str, content: str):
        self.menubar.addAction(name, 'Help', lambda: self.show(name, content))

    def show(self, name: str, content: str):
        base_path = pathlib.Path(__file__).parent
        candidates = [content, content + '.md', content + '.html']
        file_path = None
        for candidate in candidates:
            candidate_path = str(base_path / candidate)
            if os.path.exists(candidate_path):
                file_path = candidate_path
                break
        if file_path:
            win = HelpMainWindow()
            win.setSource(QUrl.fromLocalFile(file_path))
        else:
            win = HelpMainWindow(content)
        win.setWindowTitle(name)
        win.show()
        self.menubar.win = win


class HelpMainWindow(QMainWindow):
    """
    Main window for displaying help content.
    """

    def __init__(self, text: Optional[str] = None):
        super().__init__()
        self.window = HelpWindow(text)
        self.setCentralWidget(self.window)

    def setSource(self, url: QUrl):
        self.window.setSource(url)


def help_dialog(file: str, parent=None):
    """
    Show a modal help dialog for a given file.
    """
    help_window = QDialog(parent)
    help_pane = HelpWindow()
    absfile = file if os.path.isabs(file) else str((pathlib.Path(__file__).parent / file).resolve())
    help_pane.setSource(QUrl.fromLocalFile(absfile))
    help_pane.setWindowTitle('Backends')
    help_pane.show()
    layout = QVBoxLayout()
    help_window.setLayout(layout)
    layout.addWidget(help_pane)
    button_box = QDialogButtonBox(QDialogButtonBox.Ok)
    layout.addWidget(button_box)
    button_box.accepted.connect(help_window.close)
    help_window.exec()
