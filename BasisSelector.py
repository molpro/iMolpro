import copy

from PyQt5.QtWidgets import QComboBox, QWidget, QVBoxLayout, QLabel, QInputDialog


class BasisSelector(QWidget):
    new_elementRange = '- new element or range -'
    delete_elementRange = '- delete element or range -'

    def __init__(self, changed_action, null_prompt):
        super().__init__()
        self.changed_action = changed_action
        self.null_prompt = null_prompt
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.element_selector = QComboBox(self)
        layout.addWidget(self.element_selector)
        self.element_selector.currentTextChanged.connect(self.changed_element)

        self.code_selector = QComboBox(self)
        layout.addWidget(self.code_selector)
        self.code_selector.currentTextChanged.connect(self.changed_code)

    def reload(self, current_spec, possible_basis_sets):
        self.current_spec = copy.deepcopy(current_spec)
        select_ = current_spec['default'] if current_spec['default'] in possible_basis_sets else self.null_prompt
        last_element = self.element_selector.currentText()
        self.element_selector.clear()
        self.element_selector.addItem('default')
        if 'elements' in current_spec:
            self.element_selector.addItems(current_spec['elements'].keys())
            if last_element in current_spec['elements'].keys():
                self.element_selector.setCurrentText(last_element)
                if last_element in possible_basis_sets:
                    select_ = current_spec['elements'][last_element]
        self.element_selector.addItem(self.new_elementRange)
        self.code_selector.clear()
        self.code_selector.addItems([self.null_prompt] + possible_basis_sets + [self.delete_elementRange])
        self.code_selector.setCurrentText(select_)

    def changed_element(self, text):
        if text == self.new_elementRange:
            range, ok = QInputDialog.getText(self, 'New element range',
                                             'Give chemical symbol of element, or a range such as Li-Ne')
            if ok and range:
                self.element_selector.removeItem(self.element_selector.findText(self.new_elementRange))
                self.element_selector.addItem(range)
                self.element_selector.addItem(self.new_elementRange)
                self.current_spec['elements'][range] = self.current_spec['default']
                self.element_selector.setCurrentText(range)
                self.code_selector.setCurrentText(self.current_spec['default'])
                self.changed_code()
        elif text:
            self.code_selector.setCurrentText(
                self.current_spec['default'] if text == 'default' else self.current_spec['elements'][text])
        pass

    def changed_code(self):
        if self.code_selector.currentText() == self.delete_elementRange:
            if self.element_selector.currentText() == 'default':
                self.code_selector.setCurrentText(self.current_spec['default'])
            else:
                self.current_spec['elements'].pop(self.element_selector.currentText())
                index = self.element_selector.currentIndex()
                self.element_selector.setCurrentText('default')
                self.element_selector.removeItem(index)
                self.changed_action(self.current_spec)
        else:
            if self.element_selector.currentText() == 'default':
                self.current_spec['default'] = self.code_selector.currentText()
            else:
                self.current_spec['elements'][self.element_selector.currentText()] = self.code_selector.currentText()
            self.changed_action(self.current_spec)
