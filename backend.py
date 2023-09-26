import pathlib

from PyQt5.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from utilities import EditFile, MainEditFile


# from ProjectWindow import ProjectWindow


def configure_backend(parent):

    class BackendDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            backend = parent.project.property_get('backend')
            if backend:
                self.backend = backend['backend']
            else:
                self.backend = 'local'
            self.setWindowTitle('Configure backend '+self.backend)
            self.changeBackendBox = QComboBox()
            self.changeBackendBox.addItems(parent.project.backend_names())
            backendIndex = parent.project.backend_names().index(self.backend)
            self.changeBackendBox.setCurrentIndex(backendIndex)
            parameters = parent.project.backend_parameters(self.backend)
            parameters_doc = parent.project.backend_parameters(self.backend,doc=True)

            self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.reject)
            self.layout = QVBoxLayout()
            if parameters:
                self.layout.addWidget(QLabel('Parameters [to be completed]'))
                for k in parameters.keys():
                    pLayout = QHBoxLayout()
                    pLayout.addWidget(QLabel(k))
                    pLayout.addWidget(QLabel(parameters[k]))
                    pLayout.addWidget(QLabel(parameters_doc[k]))
                    pLayout.addStretch()
                    self.layout.addLayout(pLayout)
            self.switchLayout = QHBoxLayout()
            self.switchLayout.addWidget(QLabel('Change to backend:'))
            self.switchLayout.addWidget(self.changeBackendBox)
            self.layout.addLayout(self.switchLayout)
            # self.layout.addWidget(self.rawedit)
            self.layout.addWidget(self.buttonBox)
            self.setLayout(self.layout)

        def changedBackend(self):
            return self.changeBackendBox.currentText()

    while (dlg := BackendDialog(parent)) and (result := dlg.exec()) and dlg.changedBackend() != parent.project.property_get('backend')['backend']:
        parent.project.property_set({'backend': dlg.changedBackend()})
    if result:
        pass # TODO implement changes
        # print('same backend')
        # print(parent.project.properties())
