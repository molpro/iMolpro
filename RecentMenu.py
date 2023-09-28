import os

import pymolpro
from PyQt5.QtWidgets import QMenu, QAction


class RecentMenuAction(QAction):
    def __init__(self, parent, window_manager, filename: str):
        super().__init__()
        self.filename = filename
        self.parent = parent
        self.setText(self.filename.replace(os.path.expanduser('~'), '~'))
        self.triggered.connect(self.process)
        self.window_manager = window_manager

    def process(self):
        from ProjectWindow import ProjectWindow
        self.window_manager.register(ProjectWindow(self.filename, self.window_manager))
        self.parent.refresh()


class RecentMenu(QMenu):
    def __init__(self, window_manager):
        super().__init__()
        self.setTitle('Recent projects')
        self.recentProjects = []
        self.windowManager = window_manager
        self.refresh()

    def refresh(self, max_items=9):
        self.recentProjects.clear()
        self.clear()
        for i in range(1, max_items):
            f = pymolpro.recent_project('molpro', i)
            if f:
                action = RecentMenuAction(self, self.windowManager, f)
                self.recentProjects.append((f, action))
                self.addAction(action)
                if i < 10:
                    action.setShortcut('Ctrl+' + str(i))
