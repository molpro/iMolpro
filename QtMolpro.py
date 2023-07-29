from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
import sys
from Chooser import Chooser
from ProjectWindow import ProjectWindow
from WindowManager import WindowManager

if __name__ == '__main__':

    app = QApplication(sys.argv)

    windowManager = WindowManager()
    chooser = Chooser(windowManager)
    chooser.quitButton.clicked.connect(app.quit)
    windowManager.setEmptyAction(chooser.activate)
    windowManager.setFullAction(chooser.hide)

    for arg in sys.argv[1:]:
        windowManager.register(ProjectWindow(arg))

    app.exec()
