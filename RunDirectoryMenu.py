import os
import pathlib

from PyQt5.QtWidgets import QMenu, QAction, QMessageBox


class RunDirectoryMenuAction(QAction):
    def __init__(self, parent, run: int, window_manager=None):
        super().__init__()
        self.run = run
        self.parent = parent
        self.window_manager = window_manager
        self.setText(pathlib.Path(parent.project_window.project.filename('', run=run)).stem)
        self.triggered.connect(self.process)

    def process(self):
        msg = QMessageBox()
        filename = self.parent.project_window.project.filename('out', run=self.run)
        # msg.setText('Open Run Directory: ' + filename)
        # msg.exec()
        from ProjectWindow import ProjectWindow
        self.window_manager.register(ProjectWindow(filename, self.window_manager))
        self.parent.refresh()



class RunDirectoryMenu(QMenu):
    def __init__(self, project_window, window_manager):
        super().__init__()
        self.setTitle('Open Run Directory...')
        self.old_outputs = []
        self.project_window = project_window
        self.window_manager = window_manager
        self.refresh()

    def refresh(self, max_items=9):
        try:
            project = self.project_window.project
            run_directories = project.property_get('run_directories')
            if run_directories and 'run_directories' in run_directories:
                ndir = len(run_directories['run_directories'].strip().split(' '))
            else:
                ndir = 0
            nitems = min(max_items, ndir - 1)
            if nitems != len(self.old_outputs):
                self.old_outputs.clear()
                self.clear()
                for i in range(nitems ):
                    run = ndir - 1 - i
                    filename = project.filename('out', run=run)
                    if filename != project.filename('out'):
                        action = RunDirectoryMenuAction(self, run, self.window_manager)
                        self.old_outputs.append((run, action))
                        self.addAction(action)
        except:
            pass
