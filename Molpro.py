from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox
import sys
from Chooser import Chooser
from ProjectWindow import ProjectWindow
from WindowManager import WindowManager
import os

if __name__ == '__main__':

    class App(QApplication):
        def event(self, e):
            if e.type() == QEvent.FileOpen and os.path.splitext(e.file())[1] == '.molpro':
                window_manager.register(ProjectWindow(e.file()))
            else:
                return super().event(e)
            return True

    app = App(sys.argv)

    window_manager = WindowManager()
    chooser = Chooser(window_manager)
    chooser.quitButton.clicked.connect(app.quit)
    window_manager.set_empty_action(chooser.activate)
    window_manager.set_full_action(chooser.hide)

    for arg in sys.argv[1:]:
        window_manager.register(ProjectWindow(arg))

    app.exec()
