import pathlib
from utilities import force_suffix

import pymolpro
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QLabel, QWidget, QVBoxLayout, QPushButton, QFileDialog, \
    QMessageBox, QDesktopWidget

from ProjectWindow import ProjectWindow
from WindowManager import WindowManager


class Chooser(QMainWindow):
    def __init__(self, windowManager: WindowManager):
        super().__init__()
        self.windowManager = windowManager

        self.layout = QHBoxLayout()
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        LHpanel = QVBoxLayout()
        self.layout.addLayout(LHpanel)
        newButton = QPushButton('New project')
        newButton.clicked.connect(self.newProjectDialog)
        newButton.setStyleSheet(":hover { background-color: #D0D0D0 }")
        LHpanel.addWidget(newButton)
        self.recentProjects = {}

        class recentProjectButton(QPushButton):
            def __init__(self, filename, parent):
                self.parent = parent
                import os
                self.filename = os.path.expanduser(filename)
                homedir = os.path.expanduser('~')
                reducedFilename = self.filename.replace(homedir, '~')
                super().__init__(reducedFilename)
                self.clicked.connect(self.action)
                self.setStyleSheet(":hover { background-color: #D0D0D0 }")
                self.setStyleSheet("* {border: none } :hover { background-color: #D0D0D0}  ")

            def action(self):
                windowManager.register(ProjectWindow(self.filename))
                self.parent.hide()

        if pymolpro.recent_project('molpro', 1):
            box = QWidget()
            box.setStyleSheet(" background-color: #F7F7F7 ")
            self.setStyleSheet("recentProjectButton { background-color: #F7F7F7, border: none}")
            boxlayout = QVBoxLayout(box)
            LHpanel.addWidget(box)
            boxlayout.addWidget(QLabel('Open a recently-used project:'),0,QtCore.Qt.AlignLeft)
            for i in range(1, 10):
                f = pymolpro.recent_project('molpro', i)
                if f:
                    self.recentProjects[f] = recentProjectButton(f,self)
                    # self.recentProjects[f].clicked.connect(lambda: windowManager.register(lambda: ProjectWindow(f)))
                    boxlayout.addWidget(self.recentProjects[f],-1,QtCore.Qt.AlignLeft)
                else:
                    break

        existingButton = QPushButton('Open an existing project...')
        existingButton.setStyleSheet(":hover { background-color: #D0D0D0 }")
        existingButton.clicked.connect(self.openProjectDialog)
        LHpanel.addWidget(existingButton)
        self.quitButton = QPushButton('Quit')
        self.quitButton.setStyleSheet(":hover { background-color: #D0D0D0 }")
        LHpanel.addWidget(self.quitButton)

        RHpanel = QVBoxLayout()
        self.layout.addLayout(RHpanel)
        cwd = pathlib.Path(__file__).resolve().parent
        pixmap = QPixmap(str(cwd / 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png')).scaled(250, 250,
                                                                                                QtCore.Qt.KeepAspectRatio,
                                                                                                QtCore.Qt.SmoothTransformation)
        label = QLabel('')
        label.setPixmap(pixmap)
        label.resize(pixmap.width(), pixmap.height())
        RHpanel.addWidget(label)
        linkLayout = QHBoxLayout()
        RHpanel.addLayout(linkLayout)


        class linkLabel(QLabel):
            def __init__(self, text, url):
                super().__init__()
                self.setOpenExternalLinks(True)
                self.setText('<A href="' + url + '">' + text + '</A>')

        linkLayout.addWidget(linkLabel('Documentation', 'https://www.molpro.net/manual/doku.php'))
        linkLayout.addWidget(linkLabel('Molpro Manual', 'https://www.molpro.net/manual/doku.php'))

    def openProjectDialog(self):
        filename = force_suffix(QFileDialog.getExistingDirectory(self, 'Open existing project...', ))
        if filename:
            self.windowManager.register(ProjectWindow(filename))
            self.hide()

    def newProjectDialog(self):
        filename = force_suffix(QFileDialog.getSaveFileName(self, 'Save new project as ...')[0])
        if filename:
            self.windowManager.register(ProjectWindow(filename))
            self.hide()

    def activate(self):
        resolution = QDesktopWidget().screenGeometry()
        self.move((resolution.width() // 2) - (self.frameSize().width() // 2),
                  (resolution.height() // 2) - (self.frameSize().height() // 2))
        self.show()
        self.raise_()
