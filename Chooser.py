import os
import pathlib
import platform

from PyQt5.QtCore import QCoreApplication

from MenuBar import MenuBar
from RecentMenu import RecentMenu
from help import HelpManager
from utilities import force_suffix

import pymolpro
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QLabel, QWidget, QVBoxLayout, QPushButton, QFileDialog, \
    QMessageBox, QDesktopWidget, QAction

from ProjectWindow import ProjectWindow
from WindowManager import WindowManager
from settings import settings


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
        new_button = QPushButton(' &New project')
        new_button.clicked.connect(self.newProjectDialog)
        hover_css = ':hover { background-color: #D0D0D0 }'
        new_button.setStyleSheet(hover_css)
        lh_panel.addWidget(new_button)
        self.recent_project_box = QWidget()
        self.populate_recent_project_box()

        lh_panel.addWidget(self.recent_project_box)
        existing_button = QPushButton('Open an existing project...')
        existing_button.setStyleSheet(hover_css)
        existing_button.clicked.connect(self.openProjectDialog)
        lh_panel.addWidget(existing_button)
        self.quitButton = QPushButton('Quit')
        self.quitButton.setStyleSheet(hover_css)
        lh_panel.addWidget(self.quitButton)

        rh_panel = QVBoxLayout()
        self.layout.addLayout(rh_panel)
        cwd = pathlib.Path(__file__).resolve().parent
        pixmap = QPixmap(str(cwd / 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png')).scaled(250, 250,
                                                                                                QtCore.Qt.KeepAspectRatio,
                                                                                                QtCore.Qt.SmoothTransformation)
        label = QLabel('')
        label.setPixmap(pixmap)
        label.resize(pixmap.width(), pixmap.height())
        rh_panel.addWidget(label)
        link_layout = QHBoxLayout()
        rh_panel.addLayout(link_layout)

        class LinkLabel(QLabel):
            def __init__(self, text, url):
                super().__init__()
                self.setOpenExternalLinks(True)
                self.setText('<A href="' + url + '">' + text + '</A>')

        link_layout.addWidget(LinkLabel('Documentation', 'https://www.molpro.net/manual/doku.php'))
        link_layout.addWidget(LinkLabel('Molpro Manual', 'https://www.molpro.net/manual/doku.php'))

        # rh_panel.addWidget(QLabel("iMolpro version "+get_versions()['version']+'\n('+get_versions()['date']+')'))
        def version_():
            import subprocess
            import os
            version=None
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
        rh_panel.addWidget(QLabel("iMolpro version "+version_()))

        menubar = MenuBar()
        if platform.system() == 'Darwin':
            self.setMenuBar(menubar)
        menubar.addAction('New', 'File', slot=self.newProjectDialog, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addSeparator('File')
        self.recentMenu = RecentMenu(window_manager)
        menubar.addSubmenu(self.recentMenu, 'File')
        menubar.addSeparator('File')
        menubar.addAction('Quit', 'File', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')

        help_manager = HelpManager(menubar)
        help_manager.register('Overview', 'README')
        help_manager.register('Another', 'something else')
        help_manager.register('Backends', 'doc/backends.md')

    def populate_recent_project_box(self, max_items=10):

        class RecentProjectButton(QPushButton):
            def __init__(self, filename, index=None, parent=None):
                self.parent = parent
                import os
                self.filename = os.path.expanduser(filename)
                home_dir = os.path.expanduser('~')
                reduced_filename = self.filename.replace(home_dir, '~')
                super().__init__(('' if index is None or index > 9 else str(index)+': ')+reduced_filename)
                self.qaction = QAction(self)
                self.qaction.triggered.connect(self.action)
                self.clicked.connect(self.qaction.triggered)
                self.setStyleSheet(":hover { background-color: #D0D0D0 }")
                self.setStyleSheet("* {border: none } :hover { background-color: #D0D0D0}  ")

            def action(self):
                self.parent.window_manager.register(ProjectWindow(self.filename, self.parent.window_manager))
                self.parent.hide()

        self.recent_project_box.setStyleSheet(" background-color: #F7F7F7 ")
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
                self.recent_project_box.layout().addWidget(RecentProjectButton(f, i, self), -1, QtCore.Qt.AlignLeft)

    def openProjectDialog(self):
        _dir = settings['project_directory'] if 'project_directory' in settings else os.path.curdir
        filename = force_suffix(QFileDialog.getExistingDirectory(self, 'Open existing project...', _dir))
        if filename:
            self.window_manager.register(ProjectWindow(filename, self.window_manager))
            self.hide()

    def newProjectDialog(self):
        _dir = settings['project_directory'] if 'project_directory' in settings else os.path.curdir
        filename = force_suffix(QFileDialog.getSaveFileName(self, 'Save new project as ...', _dir)[0])
        if filename:
            self.window_manager.register(ProjectWindow(filename, self.window_manager))
            self.hide()

    def activate(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move((resolution.width() // 2) - (self.frameSize().width() // 2),
                  (resolution.height() // 2) - (self.frameSize().height() // 2))
        self.populate_recent_project_box()
        self.show()
        self.raise_()
