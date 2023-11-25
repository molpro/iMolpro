import os

from PyQt5.QtWidgets import QMenu, QAction


class OldOutputMenuAction(QAction):
    def __init__(self, parent, run: int):
        super().__init__()
        self.run = run
        self.parent = parent
        self.setText(os.path.basename(parent.project_window.project.filename('out', run=run)))
        self.triggered.connect(self.process)

    def process(self):
        self.parent.project_window.add_output_tab(self.run)


class OldOutputMenu(QMenu):
    def __init__(self, project_window):
        super().__init__()
        self.setTitle('Old Outputs')
        self.old_outputs = []
        self.project_window = project_window
        self.refresh()

    def refresh(self, max_items=9):
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
                    action = OldOutputMenuAction(self, run)
                    self.old_outputs.append((run, action))
                    self.addAction(action)
