try:
    from PySide6.QtWidgets import QMenuBar, QMenu
except ImportError:
    try:
        from PyQt6.QtWidgets import QMenuBar, QMenu
    except ImportError:
        from PyQt5.QtWidgets import QMenuBar, QMenu


class MenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__menus = dict()

    def addAction(self, name: str, menu_name: str, slot=None, shortcut: str = None, tooltip: str = None,
                  checkable=None):
        # print('adding action',name,menu_name,slot,shortcut,tooltip,checkable)
        if menu_name in self.__menus.keys():
            menu = self.__menus[menu_name]
        else:
            menu = self.addMenu(menu_name)
            self.__menus[menu_name] = menu
            menu.setToolTipsVisible(True)

        action = menu.addAction(name)
        if checkable is not None:
            action.setCheckable(checkable)
        if slot: action.triggered.connect(slot)
        if shortcut: action.setShortcut(shortcut)
        if tooltip: action.setToolTip(tooltip)

        action.setObjectName(name)
        return action

    def addSubmenu(self, submenu: QMenu, menu_name: str):
        if menu_name in self.__menus.keys():
            menu = self.__menus[menu_name]
        else:
            menu = self.addMenu(menu_name)
            self.__menus[menu_name] = menu
            menu.setToolTipsVisible(True)
        menu.addMenu(submenu)

    def addExistingAction(self, action, menu_name: str):
        # Inserts an already-created QAction (as opposed to addAction(),
        # which always makes a new one). Used for an action that must
        # move between windows' menus one at a time -- see
        # WindowManager.set_cli_action_owner() -- so this is a no-op if
        # the action is already in that menu.
        if menu_name in self.__menus.keys():
            menu = self.__menus[menu_name]
        else:
            menu = self.addMenu(menu_name)
            self.__menus[menu_name] = menu
            menu.setToolTipsVisible(True)
        if action not in menu.actions():
            menu.addAction(action)
        return action

    def removeExistingAction(self, action, menu_name: str):
        # Counterpart to addExistingAction: takes the action back out
        # of this menu bar's menu without deleting the QAction itself,
        # so it can be handed to a different window's menu bar.
        if menu_name in self.__menus.keys():
            menu = self.__menus[menu_name]
            if action in menu.actions():
                menu.removeAction(action)

    def addSeparator(self, menu_name: str):
        if menu_name in self.__menus.keys():
            self.__menus[menu_name].addSeparator()
