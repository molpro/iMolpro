from PyQt5.QtWidgets import QMenuBar, QMenu


class MenuBar(QMenuBar):
    def addAction(self, name: str, menu_name: str, slot=None, shortcut: str = None, tooltip: str = None, checkable=None):
        menu = None
        for a in self.actions():
            if a.menu().title() == menu_name:
                menu = a.menu()
        if not menu:
            menu = self.addMenu(menu_name)
            menu.setToolTipsVisible(True)

        action = menu.addAction(name)
        if checkable is not None:
            action.setCheckable(checkable)
        if slot: action.triggered.connect(slot)
        if shortcut: action.setShortcut(shortcut)
        if tooltip: action.setToolTip(tooltip)

        return action

    def addSubmenu(self, submenu:QMenu, menu_name: str):
        menu = None
        for a in self.actions():
            if a.menu().title() == menu_name:
                menu = a.menu()
        if not menu:
            menu = self.addMenu(menu_name)
            menu.setToolTipsVisible(True)
        menu.addMenu(submenu)

    def addSeparator(self, menu_name: str):
        for a in self.actions():
            if a.menu().title() == menu_name:
                a.menu().addSeparator()
