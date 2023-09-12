from PyQt5.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QVBoxLayout


# from ProjectWindow import ProjectWindow


def configureBackend(parent):
    print('configureBackend')

    class BackendDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle('Configure backend')
            self.chooseBox = QComboBox()
            self.chooseBox.addItem('first')
            self.chooseBox.addItem('second')
            self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.reject)
            self.layout = QVBoxLayout()
            self.layout.addWidget(self.chooseBox)
            self.layout.addWidget(self.buttonBox)
            self.setLayout(self.layout)

        def backend(self):
            return self.chooseBox.currentText()

    dlg = BackendDialog(parent)
    if dlg.exec():
        print("OK!", parent.project.property_get('backend'), dlg.backend())
        print(parent.project)
        print(parent.project.properties())
        backend_ = {'backend', dlg.backend()}
        print(type(backend_))
        parent.project.property_set(backend_)
    else:
        print("No!")
