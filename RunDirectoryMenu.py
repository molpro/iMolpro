import logging

logger = logging.getLogger(__name__)
import pathlib

from PyQt5.QtWidgets import QMenu, QAction, QMessageBox


class RunDirectoryMenuAction(QAction):
    def __init__(self, project_window, run: int):
        super().__init__()
        self.run = run
        self.project_window = project_window
        self.setText(pathlib.Path(project_window.project.filename('', run=run)).stem)
        self.triggered.connect(self.process)


class RunDirectoryMenuActionOpenRun(RunDirectoryMenuAction):
    def process(self):
        filename = pathlib.Path(self.project_window.project.filename('out', run=self.run)).parent.as_posix()
        from ProjectWindow import ProjectWindow
        self.project_window.window_manager.register(
            ProjectWindow(filename, self.project_window.window_manager, record_as_recent=False))


class RunDirectoryMenuActionOldOutputs(RunDirectoryMenuAction):
    def process(self):
        self.project_window.add_output_tab(self.run)


class RunDirectoryMenuActionShow(RunDirectoryMenuAction):
    def process(self):
        self.project_window.switch_run_directory(self.run)


class RunDirectoryMenuActionDelete(RunDirectoryMenuAction):
    def process(self):
        self.project_window.project.run_delete(self.run)


class RunDirectoryMenus:
    menu_items = {
        'Show Run...': RunDirectoryMenuActionShow,
        'Open Run as Project...': RunDirectoryMenuActionOpenRun,
        'Erase Run...': RunDirectoryMenuActionDelete,
        'Show Run Output...': RunDirectoryMenuActionOldOutputs,
    }

    def __init__(self, project_window, menubar, menu_name='Runs'):
        self.project_window = project_window
        self.menus = {}
        for menu_item_name, action_class in self.menu_items.items():
            self.menus[menu_item_name] = RunDirectoryMenu(menu_item_name, action_class, project_window)
            menubar.addSubmenu(self.menus[menu_item_name], menu_name)

    def refresh(self):
        for menu in self.menus.values():
            menu.refresh()


class RunDirectoryMenu(QMenu):
    def __init__(self, title: str, action_class: RunDirectoryMenuAction, project_window):
        super().__init__()
        self.setTitle(title)
        self.action_class = action_class
        self.project_window = project_window
        self.run_directories = []
        self.refresh()

    def refresh(self, max_items=9):
        try:
            run_directories = self.project_window.project.run_directory_names
            if run_directories == self.run_directories: return
            self.run_directories = run_directories
            self.clear()
            self.action_buffer = []
            for run in range(len(run_directories) - 1, 0, -1):
                action = self.action_class(self.project_window, run)
                self.action_buffer.append((run, action))
                self.addAction(action)
        except:
            logger.debug('exception in RunDirectoryMenu refresh')
