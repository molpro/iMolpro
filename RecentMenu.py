import os

import pymolpro
from PyQt5.QtWidgets import QMenu, QAction


def projectWindowRegister(windowManager, filename):
    from ProjectWindow import ProjectWindow
    windowManager.register(ProjectWindow(filename, windowManager))
class RecentMenuAction(QAction):
    def __init__(self, parent, windowManager, filename:str):
        super().__init__()
        self.filename = filename
        self.parent = parent
        self.setText(self.filename.replace(os.path.expanduser('~'), '~'))
        self.triggered.connect(self.process)
        self.windowManager=windowManager

    def process(self):
        projectWindowRegister(self.windowManager, self.filename)
        self.parent.refresh()
class RecentMenu(QMenu):
    def __init__(self, windowManager, maxItems=9):
        super().__init__()
        self.setTitle('Recent projects')
        self.recentProjects = []
        self.windowManager=windowManager
        self.refresh()

    def refresh(self, maxItems=9):
        self.recentProjects.clear()
        self.clear()
        for i in range(1, maxItems):
            f = pymolpro.recent_project('molpro', i)
            if f:
                action = RecentMenuAction(self,self.windowManager,f)
                self.recentProjects.append((f, action))
                self.addAction(action)
                if i < 10:
                    action.setShortcut('Ctrl+'+str(i))

