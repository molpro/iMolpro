from PyQt5.QtWidgets import QApplication
import sys
from Chooser import Chooser
from ProjectWindow import ProjectWindow


class WindowManager:
    def __init__(self):
        self.openWindows = []
        self.emptyAction = None
        self.fullAction = None

    def register(self, widget: QWidget):
        if self.fullAction and not self.openWindows:
            self.fullAction()
        self.openWindows.append(widget)

    def unregister(self, widget: QWidget):
        self.openWindows.remove(widget)
        if self.emptyAction and not self.openWindows:
            self.emptyAction()

    def setEmptyAction(self, fun):
        self.emptyAction = fun
        if not self.openWindows:
            self.emptyAction()

    def setFullAction(self, fun):
        self.fullAction = fun


if __name__ == '__main__':
    app = QApplication(sys.argv)

    chooser = Chooser()
    windowManager = WindowManager()
    windowManager.setEmptyAction(chooser.show)
    windowManager.setFullAction(chooser.hide)
    for arg in sys.argv[1:]:
        window = ProjectWindow(arg)
        windowManager.register(window)
        window.closeSignal.connect(windowManager.unregister)
        window.show()

    app.exec()
