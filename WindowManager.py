from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox
from utilities import force_suffix


class WindowManager:
    def __init__(self):
        self.openWindows = []
        self.emptyAction = None
        self.fullAction = None

    def register(self, widget: QWidget):
        if self.fullAction and not self.openWindows:
            self.fullAction()
        self.openWindows.append(widget)
        widget.close_signal.connect(self.unregister)
        widget.new_signal.connect(self.new)
        widget.chooser_signal.connect(self.emptyAction)
        widget.show()

    def unregister(self, widget: QWidget):
        self.openWindows.remove(widget)
        if self.emptyAction and not self.openWindows:
            self.emptyAction()

    def set_empty_action(self, fun):
        self.emptyAction = fun
        if not self.openWindows:
            self.emptyAction()

    def set_full_action(self, fun):
        self.fullAction = fun

    def new(self, data):
        filename = force_suffix(QFileDialog.getSaveFileName(caption='Save new project as ...')[0])
        if filename:
            self.register(type(data)(filename, self))
