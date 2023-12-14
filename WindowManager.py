import os
import shutil

from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from utilities import force_suffix
from settings import settings


class WindowManager:
    def __init__(self):
        self.openWindows = []
        self.emptyAction = None
        self.fullAction = None

    def register(self, widget: QWidget):
        if widget is None or (hasattr(widget, 'invalid') and widget.invalid):
            return
        if self.fullAction and not self.openWindows:
            self.fullAction()
        self.openWindows.append(widget)
        widget.close_signal.connect(self.unregister)
        widget.new_signal.connect(self.new)
        widget.chooser_signal.connect(self.emptyAction)
        widget.show()

    def unregister(self, widget: QWidget):
        self.openWindows.remove(widget)
        if self.emptyAction and not self.openWindows:
            self.emptyAction()

    def set_empty_action(self, fun):
        self.emptyAction = fun
        if not self.openWindows:
            self.emptyAction()

    def set_full_action(self, fun):
        self.fullAction = fun

    def new(self, data):
        from ProjectWindow import ProjectWindow
        _dir = settings['project_directory'] if 'project_directory' in settings else os.path.curdir
        while True:
            filename = force_suffix(QFileDialog.getSaveFileName(data, 'Save new project as ...', _dir,
                                                                options=QFileDialog.DontConfirmOverwrite)[0])
            if filename:
                if os.path.exists(filename):
                    QMessageBox.critical(data, 'Project already exists',
                                         filename + ' already exists; please choose another file name')
                else:
                    self.register(ProjectWindow(filename, self))
                    return
            else:
                return
