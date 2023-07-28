from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
import sys
from Chooser import Chooser
from ProjectWindow import ProjectWindow
from WindowManager import WindowManager

if __name__ == '__main__':

    class newProject():
        def __init__(self,windowManager,file):
            print('newProject',file)
            window = ProjectWindow(file)
            windowManager.register(window)
            window.closeSignal.connect(windowManager.unregister)
            window.show()

    app = QApplication(sys.argv)

    windowManager = WindowManager()
    chooser = Chooser(windowManager)
    chooser.quitButton.clicked.connect(app.quit)
    # for k,v in chooser.recentProjects.items():
    #     v.clicked.connect(lambda: newProject(windowManager,k))
    windowManager.setEmptyAction(chooser.show)
    windowManager.setFullAction(chooser.hide)

    for arg in sys.argv[1:]:
        windowManager.register(ProjectWindow(arg))

    app.exec()
