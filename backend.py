from PyQt5.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel


def configure_backend(parent):
    class BackendDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            backend = parent.project.property_get('backend')
            if backend:
                self.backend = backend['backend']
            else:
                self.backend = 'local'
            self.setWindowTitle('Configure backend ' + self.backend)
            self.change_backend_box = QComboBox()
            self.change_backend_box.addItems(parent.project.backend_names())
            backend_index = parent.project.backend_names().index(self.backend)
            self.change_backend_box.setCurrentIndex(backend_index)
            parameters = parent.project.backend_parameters(self.backend)
            parameters_doc = parent.project.backend_parameters(self.backend, doc=True)

            self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)
            self.layout = QVBoxLayout()
            if parameters:
                self.layout.addWidget(QLabel('Parameters [to be completed]'))
                for k in parameters.keys():
                    p_layout = QHBoxLayout()
                    p_layout.addWidget(QLabel(k))
                    p_layout.addWidget(QLabel(parameters[k]))
                    p_layout.addWidget(QLabel(parameters_doc[k]))
                    p_layout.addStretch()
                    self.layout.addLayout(p_layout)
            self.switch_layout = QHBoxLayout()
            self.switch_layout.addWidget(QLabel('Change to backend:'))
            self.switch_layout.addWidget(self.change_backend_box)
            self.layout.addLayout(self.switch_layout)
            # self.layout.addWidget(self.rawedit)
            self.layout.addWidget(self.button_box)
            self.setLayout(self.layout)

        def changed_backend(self):
            return self.change_backend_box.currentText()

    while (dlg := BackendDialog(parent)) and (result := dlg.exec()) and dlg.changed_backend() != \
            parent.project.property_get('backend')['backend']:
        parent.project.property_set({'backend': dlg.changed_backend()})
    if result:
        pass  # TODO implement changes
