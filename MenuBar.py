from PySide6.QtWidgets import QMenuBar, QMenu


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

    def addSeparator(self, menu_name: str):
        if menu_name in self.__menus.keys():
            self.__menus[menu_name].addSeparator()
