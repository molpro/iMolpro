from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox
import sys
from Chooser import Chooser
from ProjectWindow import ProjectWindow
from WindowManager import WindowManager

if __name__ == '__main__':

    class App(QApplication):
        def event(self, e):
            if e.type() == QEvent.FileOpen:
                windowManager.register(ProjectWindow(e.file()))
            else:
                return super().event(e)
            return True

    app = App(sys.argv)

    windowManager = WindowManager()
    chooser = Chooser(windowManager)
    chooser.quitButton.clicked.connect(app.quit)
    windowManager.setEmptyAction(chooser.activate)
    windowManager.setFullAction(chooser.hide)

    for arg in sys.argv[1:]:
        windowManager.register(ProjectWindow(arg))

    app.exec()
