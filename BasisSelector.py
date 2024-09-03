from PyQt5.QtWidgets import QComboBox


class BasisSelector(QComboBox):
    def __init__(self, changed_action):
        super().__init__()
        self.changed_action = changed_action
        self.currentTextChanged.connect(self.changed)

    def clear(self):
        super().clear()

    def addItems(self, items):
        super().addItems(items)
    def reload(self,possible_basis_sets, null_prompt,select):
        self.clear()
        self.addItems([null_prompt] + possible_basis_sets)
        self.setCurrentText(select)

    def changed(self):
       self.changed_action({'default':self.currentText(), 'elements':{}})
