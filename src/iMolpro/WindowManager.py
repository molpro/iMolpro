import os
import shutil

try:
    from PySide6.QtWidgets import QWidget, QFileDialog, QMessageBox
except ImportError:
    try:
        from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox
    except ImportError:
        from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from .utilities import force_suffix
from .settings import settings
from . import cli_install
from . import cli_install_ui


class WindowManager:
    def __init__(self):
        self.openWindows = []
        self.emptyAction = None
        self.fullAction = None
        self.cli_install_action = None
        self.cli_install_action_owner = None

    def get_cli_install_action(self):
        """The single, shared 'Install command line tool...' QAction,
        created lazily on first use. Returns None where the feature
        isn't applicable (not a frozen macOS app)."""
        if self.cli_install_action is None and cli_install.available():
            self.cli_install_action = cli_install_ui.make_cli_install_action()
        return self.cli_install_action

    def set_cli_action_owner(self, menubar):
        """Move the shared CLI-install action into `menubar`'s Edit
        menu, taking it out of wherever it previously lived first.

        On macOS, Qt's native Application-menu merging is keyed to
        which top-level windows currently have the action somewhere in
        their own menu bar -- not to which single window is active --
        so simply adding the same QAction to every window's menu bar
        (as done previously) still shows one copy per window that has
        it, rather than de-duplicating by the action's identity. The
        only way to get exactly one, always, is to make sure it is
        only ever present in one window's menu bar at a time, and move
        it explicitly whenever a different window becomes active (see
        the changeEvent overrides in Chooser and ProjectWindow)."""
        action = self.get_cli_install_action()
        if action is None or self.cli_install_action_owner is menubar:
            return
        if self.cli_install_action_owner is not None:
            self.cli_install_action_owner.removeExistingAction(action, 'Edit')
        menubar.addExistingAction(action, 'Edit')
        self.cli_install_action_owner = menubar

    def register(self, widget: QWidget):
        if widget is None or (hasattr(widget, 'invalid') and widget.invalid):
            return
        if self.fullAction and not self.openWindows:
            self.fullAction()
        self.openWindows.append(widget)
        widget.close_signal.connect(self.unregister)
        widget.new_signal.connect(self.new)
        widget.chooser_signal.connect(self.emptyAction)
        if 'project_window_width' in settings and 'project_window_height' in settings:
            widget.resize(settings['project_window_width'], settings['project_window_height'])
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
        from .ProjectWindow import ProjectWindow
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
