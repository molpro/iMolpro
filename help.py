import pathlib

from PyQt5.QtWidgets import QTextBrowser, QMainWindow, QShortcut, QWidget, QHBoxLayout, QDialog, QVBoxLayout, \
    QDialogButtonBox
from PyQt5.QtCore import Qt, QUrl
from MenuBar import MenuBar


class HelpWindow(QWidget):
    def __init__(self, text=None):
        super().__init__()
        layout = QHBoxLayout(self)
        self.setLayout(layout)
        self.browser = QTextBrowser()
        layout.addWidget(self.browser)
        if text:
            self.browser.setText(text)
        self.browser.setOpenExternalLinks(True)
        # self.setCentralWidget(self.browser)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.shortcutClose = QShortcut('Ctrl+W', self)
        self.shortcutClose.activated.connect(self.close)

    def setSource(self, file):
        self.browser.setSource(file)


class HelpManager:
    def __init__(self, menubar: MenuBar):
        self.menubar = menubar

    def register(self, name: str, content: str):
        self.menubar.addAction(name, 'Help', lambda: self.show(name, content))

    def show(self, name, content):
        import os
        _file = str(pathlib.Path(__file__).parent / content)
        if not os.path.exists(_file):
            _file = str(pathlib.Path(__file__).parent / (content + '.md'))
        if not os.path.exists(_file):
            _file = str(pathlib.Path(__file__).parent / (content + '.html'))
        if not os.path.exists(_file):
            self.menubar.win = HelpWindow(content)
        else:
            self.menubar.win = HelpWindow()
            self.menubar.win.setSource(QUrl(_file))
        self.menubar.win.setWindowTitle(name)
        self.menubar.win.show()

def help_dialog(file, parent=None):
    help_window = QDialog(parent)
    help_pane = HelpWindow()
    help_pane.setSource(QUrl(file))
    help_pane.setWindowTitle('Backends')
    help_pane.show()
    layout = QVBoxLayout()
    help_window.setLayout(layout)
    layout.addWidget(help_pane)
    button_box = QDialogButtonBox(QDialogButtonBox.Ok)
    layout.addWidget(button_box)
    button_box.accepted.connect(help_window.close)
    help_window.exec()

