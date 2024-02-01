import os
import pathlib
import platform

from PyQt5.QtCore import QCoreApplication, Qt, QUrl

from MenuBar import MenuBar
from RecentMenu import RecentMenu
from help import HelpManager
from utilities import force_suffix

import pymolpro
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QKeySequence, QDesktopServices, QGuiApplication
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QLabel, QWidget, QVBoxLayout, QPushButton, QFileDialog, \
    QDesktopWidget, QAction, QShortcut, QToolButton

from ProjectWindow import ProjectWindow
from WindowManager import WindowManager
from settings import settings, settings_edit


class PushButton(QPushButton):
    def enterEvent(self, ev, QEnterEvent=None):
        self.setCursor(Qt.PointingHandCursor)

    def exitEvent(self, ev, QExitEvent=None):
        self.setCursor(Qt.ArrowCursor)


class Chooser(QMainWindow):
    def __init__(self, window_manager: WindowManager):
        super().__init__()
        self.window_manager = window_manager

        self.layout = QHBoxLayout()
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        lh_panel = QVBoxLayout()
        self.layout.addLayout(lh_panel)
        new_button = PushButton('&New project')
        new_button.clicked.connect(self.newProjectDialog)
        # hover_css = ':hover { border: none; background-color: #D0D0D0 }'
        # new_button.setStyleSheet(hover_css)
        lh_panel.addWidget(new_button)
        self.recent_project_box = QWidget()
        self.populate_recent_project_box()

        lh_panel.addWidget(self.recent_project_box)
        existing_button = PushButton('&Open an existing project...')
        # existing_button.setStyleSheet(hover_css)
        existing_button.clicked.connect(self.openProjectDialog)
        lh_panel.addWidget(existing_button)
        self.quitButton = PushButton('&Quit')
        # self.quitButton.setStyleSheet(hover_css)
        lh_panel.addWidget(self.quitButton)

        rh_panel = QVBoxLayout()
        self.layout.addLayout(rh_panel)
        cwd = pathlib.Path(__file__).resolve().parent

        class LinkImage(QLabel):
            def __init__(self, image, url=None, width=250, height=250):
                super().__init__()
                ratio = QGuiApplication.primaryScreen().devicePixelRatio()
                self.setPixmap(QPixmap(image).scaled(int(width * ratio), int(height * ratio), Qt.KeepAspectRatio,
                                                     QtCore.Qt.SmoothTransformation))
                self.pixmap().setDevicePixelRatio(ratio)
                self.url = QUrl(url)
                self.setAlignment(Qt.AlignCenter)

            def mousePressEvent(self, event):
                if self.url is not None:
                    QDesktopServices.openUrl(self.url)

            def enterEvent(self, ev, QEnterEvent=None):
                self.setCursor(Qt.PointingHandCursor)

            def exitEvent(self, ev, QExitEvent=None):
                self.setCursor(Qt.ArrowCursor)

        label = LinkImage(str(cwd / 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png'), 'https://www.molpro.net', 186,
                          217)  # predicated on 3139 x 3475 image
        label.setContentsMargins(0, 30, 0, 20)
        rh_panel.addWidget(label)
        link_layout = QHBoxLayout()
        rh_panel.addLayout(link_layout)

        class LinkLabel(QLabel):
            def __init__(self, text, url):
                super().__init__()
                self.setOpenExternalLinks(True)
                self.setText('<A style="text-decoration:none;color:black" href="' + url + '">' + text + '</A>')
                self.setStyleSheet('color: black')

        helpButton = PushButton('Help', self)
        helpButton.clicked.connect(lambda: help_manager.show('Help', 'README'))
        self.shortcutHelp = QShortcut(QKeySequence.HelpContents, self)
        self.shortcutHelp.activated.connect(self.close)
        # helpButton.setStyleSheet(":hover {border: none ; background-color: #D0D0D0}  ")
        link_layout.addWidget(helpButton)
        # manual_button = LinkLabel('Molpro Manual', 'https://www.molpro.net/manual/doku.php')
        manual_button = PushButton('Molpro Manual', self)
        # manual_button.setStyleSheet(":hover {border: none ; background-color: #D0D0D0}  ")
        manual_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://www.molpro.net/manual/doku.php')))
        link_layout.addWidget(manual_button)

        # rh_panel.addWidget(QLabel("iMolpro version "+get_versions()['version']+'\n('+get_versions()['date']+')'))
        def version_():
            import subprocess
            import os
            version = None
            if os.path.exists(pathlib.Path(__file__).resolve().parent / '.git'):
                try:
                    version = subprocess.check_output(['git', 'describe', '--tags', '--dirty']).decode('ascii').strip()
                except Exception:
                    pass
                if version:
                    return version
            version_file = pathlib.Path(__file__).resolve().parent / 'VERSION'
            if os.path.exists(version_file):
                version = open(version_file, 'r').read().strip()
            if version:
                return version
            else:
                return 'unknown'

        version_label = LinkLabel("iMolpro version " + version_(), 'https://github.com/molpro/iMolpro/tree/'+version_())
        version_label.setStyleSheet("font-size: 10px")
        version_label.setAlignment(Qt.AlignCenter)
        rh_panel.addWidget(version_label)

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.showNormal()
        menubar = MenuBar()
        menubar.addAction('New', 'Projects', slot=self.newProjectDialog, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addAction('Open', 'Projects', slot=self.openProjectDialog, shortcut='Ctrl+O',
                          tooltip='Open an existing project')
        menubar.addSeparator('Projects')
        self.recentMenu = RecentMenu(window_manager)
        menubar.addSubmenu(self.recentMenu, 'Projects')
        menubar.addSeparator('Projects')
        menubar.addAction('Quit', 'Projects', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')
        menubar.addAction('Settings', 'Edit', lambda arg, parent=self: settings_edit(parent), tooltip='Edit settings')

        help_manager = HelpManager(menubar)
        help_manager.register('Overview', 'README')
        help_manager.register('Example', 'doc/example.md')
        help_manager.register('Backends', 'doc/backends.md')
        help_manager.register('Display', 'doc/display.md')

        if platform.system() == 'Darwin':
            self.setMenuBar(menubar)
        else:
            self.shortcutQuit = QShortcut(QKeySequence("Ctrl+Q"), self)
            self.shortcutQuit.activated.connect(QCoreApplication.quit)
            self.shortcutNew = QShortcut(QKeySequence("Ctrl+N"), self)
            self.shortcutNew.activated.connect(self.newProjectDialog)
            self.shortcutOpen = QShortcut(QKeySequence("Ctrl+O"), self)
            self.shortcutOpen.activated.connect(self.openProjectDialog)

    def populate_recent_project_box(self, max_items=10):

        class RecentProjectButton(QToolButton):
            def __init__(self, filename, index=None, parent=None):
                self.parent = parent
                import os
                self.filename = os.path.expanduser(filename)
                home_dir = os.path.expanduser('~')
                reduced_filename = self.filename.replace(home_dir, '~')
                super().__init__(parent)
                max_length = 60
                self.setText(('' if index is None or index > 9 else '&' + str(index) + ': ') + (
                    reduced_filename if len(reduced_filename) <= max_length else ' ... ' + reduced_filename[
                                                                                           -max_length + 5:]))
                self.setContentsMargins(0, 0, 0, 0)

                self.qaction = QAction(self)
                if index <= 9:
                    self.setShortcut('Ctrl+' + str(index))
                self.qaction.triggered.connect(self.action)
                self.clicked.connect(self.qaction.triggered)
                self.setStyleSheet("* {border: none } :hover { background-color: #F0F0F0}  ")
                # self.setStyleSheet("* {border: none }")

            def enterEvent(self, ev, QEnterEvent=None):
                self.setCursor(Qt.PointingHandCursor)

            def exitEvent(self, ev, QExitEvent=None):
                self.setCursor(Qt.ArrowCursor)

            def action(self):
                self.parent.window_manager.register(ProjectWindow(self.filename, self.parent.window_manager))
                self.parent.hide()

        self.recent_project_box.setStyleSheet(" background-color: #F7F7F7 ")
        self.recent_project_box.setMaximumWidth(400)
        self.recent_project_box.setFixedWidth(400)
        if not self.recent_project_box.layout():
            QVBoxLayout(self.recent_project_box)
        layout = self.recent_project_box.layout()
        for item in [layout.itemAt(i) for i in range(layout.count())]:
            self.recent_project_box.layout().removeItem(item)
            item.widget().setParent(None)
        self.recent_project_box.layout().addWidget(QLabel('Open a recently-used project:'), 0, QtCore.Qt.AlignLeft)
        for i in range(1, max_items):
            f = pymolpro.recent_project('molpro', i)
            if f:
                button = RecentProjectButton(f, i, self)
                self.recent_project_box.layout().addWidget(button, -1, QtCore.Qt.AlignLeft)

    def openProjectDialog(self):
        _dir = settings['project_directory'] if 'project_directory' in settings else os.path.curdir
        if platform.system() == 'Darwin':
            filename, filter = QFileDialog.getOpenFileName(self, 'Open existing project...', _dir,
                                                           filter='Molpro projects (*.molpro)')
        else:
            filename = force_suffix(QFileDialog.getExistingDirectory(self, 'Open existing project...', _dir))
        if filename:
            self.window_manager.register(ProjectWindow(filename, self.window_manager))
            self.hide()

    def newProjectDialog(self):
        self.window_manager.new(self)
        if len(self.window_manager.openWindows) > 0:
            self.hide()

    def activate(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move((resolution.width() // 2) - (self.frameSize().width() // 2),
                  (resolution.height() // 2) - (self.frameSize().height() // 2))
        self.populate_recent_project_box()
        self.show()
        self.raise_()
