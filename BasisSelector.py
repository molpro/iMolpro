from PyQt5.QtWidgets import QComboBox, QWidget, QVBoxLayout


class BasisSelector(QWidget):
    def __init__(self, changed_action):
        super().__init__()
        self.changed_action = changed_action
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.combo = QComboBox(self)
        layout.addWidget(self.combo)
        self.combo.currentTextChanged.connect(self.changed)

    def reload(self, possible_basis_sets, null_prompt, select):
        self.combo.clear()
        self.combo.addItems([null_prompt] + possible_basis_sets)
        self.combo.setCurrentText(select)

    def changed(self):
        self.changed_action({'default': self.combo.currentText(), 'elements': {}})
