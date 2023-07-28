from PyQt5.QtWidgets import QWidget


class WindowManager:
    def __init__(self):
        self.openWindows = []
        self.emptyAction = None
        self.fullAction = None

    def register(self, widget: QWidget):
        if self.fullAction and not self.openWindows:
            self.fullAction()
        self.openWindows.append(widget)
        widget.closeSignal.connect(self.unregister)
        widget.show()

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
