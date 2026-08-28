import os
import pathlib
from typing import Optional

try:
    from PySide6.QtWidgets import QTextBrowser, QMainWindow, QWidget, QHBoxLayout, QDialog, QVBoxLayout, \
        QDialogButtonBox, QMessageBox, QApplication
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QKeySequence, QDesktopServices, QShortcut, QAction
except ImportError:
    try:
        from PyQt6.QtWidgets import QTextBrowser, QMainWindow, QWidget, QHBoxLayout, QDialog, QVBoxLayout, \
            QDialogButtonBox, QMessageBox, QApplication
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QKeySequence, QDesktopServices, QShortcut, QAction
    except ImportError:
        from PyQt5.QtWidgets import QTextBrowser, QMainWindow, QWidget, QHBoxLayout, QDialog, QVBoxLayout, \
            QDialogButtonBox, QShortcut, QMessageBox, QApplication, QAction
        from PyQt5.QtCore import Qt, QUrl
        from PyQt5.QtGui import QKeySequence, QDesktopServices

try:
    AboutRole = QAction.AboutRole
except AttributeError:
    AboutRole = QAction.MenuRole.AboutRole

from .MenuBar import MenuBar
from ._paths import app_root
from . import full_version


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

    def register_url(self, name: str, url: str):
        self.menubar.addAction(name, 'Help',
                          lambda: QDesktopServices.openUrl(QUrl(url)))

    def show(self, name: str, content: str):
        base_path = app_root()
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
    absfile = file if os.path.isabs(file) else str((app_root() / file).resolve())
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

def _package_version(package_name: str) -> str:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:  # pragma: no cover - Python < 3.8
        from importlib_metadata import version, PackageNotFoundError
    try:
        return version(package_name)
    except PackageNotFoundError:
        return 'unknown'


def show_about_dialog(parent=None):
    """
    The standard "About" dialog, showing iMolpro's own version alongside
    those of the pymolpro and sjef (pysjef) packages that actually drive
    project management and Molpro execution underneath iMolpro.
    """

    def _version_line(name: str, version=None) -> str:
        return f"{name}: {version if version is not None else _package_version(name)}"

    text = \
        "<h3>" + _version_line("iMolpro", full_version()) + "</h3>" + \
        f"Contains<br>" + \
        "<br>".join([_version_line(name) for name in ["pymolpro", "pysjef", "PySide6", "vtk"]])
    QMessageBox.about(parent, 'About iMolpro', text)


def help_manager_default(menubar: MenuBar):
    help_manager = HelpManager(menubar)
    help_manager.register('Overview', 'README')
    help_manager.register('Example', 'doc/example.md')
    help_manager.register('Backends', 'doc/backends.md')
    help_manager.register('Runs', 'doc/runs.md')
    help_manager.register('Display', 'doc/display.md')
    help_manager.register_url('Jmol reference', 'https://jmol.sourceforge.net/docs')
    menubar.addSeparator('Help')
    about_action = menubar.addAction('About iMolpro', 'Help',
                                      lambda: show_about_dialog(QApplication.activeWindow()))
    # AboutRole makes Qt relocate this item to the standard place on each
    # platform: the application menu on macOS (regardless of which menu
    # it was added to here), and left in place -- the end of the Help
    # menu, also the Windows/Linux convention -- everywhere else.
    about_action.setMenuRole(AboutRole)
    return help_manager