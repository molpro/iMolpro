import copy

from PyQt5.QtWidgets import QComboBox, QWidget, QLabel, QInputDialog, QGridLayout, QPushButton


class BasisSelector(QWidget):
    new_elementRange = '- new element or range -'
    delete_elementRange = '- delete element or range -'

    def __init__(self, changed_action, null_prompt):
        super().__init__()
        self.changed_action = changed_action
        self.null_prompt = null_prompt
        layout = QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def reload(self, current_spec=None, possible_basis_sets=None):
        if possible_basis_sets is not None:
            self.possible_basis_sets = possible_basis_sets
        if current_spec is not None:
            self.current_spec = copy.deepcopy(current_spec)

        for i in reversed(range(self.layout().count())):
            widgetToRemove = self.layout().itemAt(i).widget()
            self.layout().removeWidget(widgetToRemove)
            widgetToRemove.setParent(None)

        self.layout().addWidget(QLabel('Default'), 0, 0)
        default_selector = QComboBox(self)
        self.layout().addWidget(default_selector, 0, 1)
        default_selector.currentTextChanged.connect(lambda: self.changed_code(default_selector, 'default'))
        select_ = self.current_spec['default'] if self.current_spec[
                                                      'default'] in self.possible_basis_sets else self.null_prompt
        default_selector.clear()
        default_selector.addItems([self.null_prompt] + self.possible_basis_sets)
        default_selector.setCurrentText(select_)

        if 'elements' in self.current_spec:
            count = 1
            for k, v in self.current_spec['elements'].items():
                self.layout().addWidget(QLabel(k), count, 0)
                code_selector = QComboBox(self)
                code_selector.addItems([self.null_prompt] + self.possible_basis_sets + [self.delete_elementRange])
                code_selector.currentTextChanged.connect(lambda: self.changed_code(code_selector, k))
                self.layout().addWidget(code_selector, count, 1)
                count += 1
                select_ = self.current_spec['elements'][k]
                if select_ in self.possible_basis_sets:
                    code_selector.setCurrentText(select_)

            new_element_button = QPushButton('Specific element')
            self.layout().addWidget(new_element_button, count, 0, 1, 2)
            new_element_button.clicked.connect(self.new_element)

    def new_element(self):
        range, ok = QInputDialog.getText(self, 'New element range',
                                         'Give chemical symbol of element, or a range such as Li-Ne')
        if ok and range:
            self.current_spec['elements'][range] = self.current_spec['default']
            self.reload()

    def changed_code(self, selector, code):
        if selector.currentText() == self.delete_elementRange:
            self.current_spec['elements'].pop(code)
            self.changed_action(self.current_spec)
            self.reload()
        else:
            if code == 'default':
                self.current_spec['default'] = selector.currentText()
            else:
                self.current_spec['elements'][code] = selector.currentText()
            self.changed_action(self.current_spec)
