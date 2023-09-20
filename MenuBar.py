from PyQt5.QtWidgets import QMenuBar


class MenuBar(QMenuBar):
    def addAction(self, name: str, menuName: str, slot=None, shortcut: str = None, tooltip: str = None, checkable=None):
        menu = None
        for a in self.actions():
            if a.menu().title() == menuName:
                menu = a.menu()
        if not menu:
            menu = self.addMenu(menuName)
            menu.setToolTipsVisible(True)

        action = menu.addAction(name)
        if checkable is not None:
            action.setCheckable(checkable)
        if slot: action.triggered.connect(slot)
        if shortcut: action.setShortcut(shortcut)
        if tooltip: action.setToolTip(tooltip)

        return action

    def addSeparator(self, menuName: str):
        for a in self.actions():
            if a.menu().title() == menuName:
                a.menu().addSeparator()
