import pathlib

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QLabel
except ImportError:
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QLabel
    except ImportError:
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QLabel

from .project import Project


class StatusBar(QLabel):
    def __init__(self, project: Project, run_actions: list, kill_actions: list, latency=1000):
        super().__init__()
        self.project = project
        self.run_actions = run_actions
        self.kill_actions = kill_actions
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(latency)

    def refresh(self):
        try:
            self.setText('Status: ' + ('run ' + pathlib.Path(
                self.project.filename()).stem + ' ' if self.project.filename() != self.project.filename(
                run=-1) else '') + self.project.status)
            for run_action in self.run_actions:
                run_action.setDisabled(not self.project.run_needed())
            for kill_action in self.kill_actions:
                kill_action.setDisabled(self.project.status != 'running' and self.project.status != 'waiting')
        except:
            pass
