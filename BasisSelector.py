import copy

from PyQt5.QtWidgets import QComboBox, QWidget, QVBoxLayout, QLabel, QInputDialog


class BasisSelector(QWidget):
    new_elementRange = '- new element or range -'
    def __init__(self, changed_action, null_prompt):
        super().__init__()
        self.changed_action = changed_action
        self.null_prompt = null_prompt
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.element_selector = QComboBox(self)
        layout.addWidget(self.element_selector)
        self.element_selector.currentTextChanged.connect(self.changed_element)

        self.code_selector = QComboBox(self)
        layout.addWidget(self.code_selector)
        self.code_selector.currentTextChanged.connect(self.changed_code)

    def reload(self, current_spec, possible_basis_sets):
        self.current_spec = copy.deepcopy(current_spec)
        self.element_selector.clear()
        self.element_selector.addItem('default')
        if 'elements' in current_spec:
            self.element_selector.addItems(current_spec['elements'].keys())
        self.element_selector.addItem(self.new_elementRange)
        select_ = self.null_prompt if current_spec['elements'] or not current_spec['default'] in possible_basis_sets else \
        current_spec['default']
        self.code_selector.clear()
        self.code_selector.addItems([self.null_prompt] + possible_basis_sets + ['- delete -'])
        self.code_selector.setCurrentText(select_)

    def changed_element(self, text):
        print('changed_element', text)
        if text == self.new_elementRange:
            print('new elementRange')
            range, ok = QInputDialog.getText(self, 'New element range','Give chemical symbol of element, or a range such as Li-Ne')
            if ok and range:
                print('selected',range)
                self.element_selector.addItem(range)
                self.current_spec['elements'][range] = self.current_spec['default']
                print('current spec changed to',self.current_spec)
                self.element_selector.setCurrentText(range)
        elif text:
            self.code_selector.setCurrentText(self.current_spec['default'] if text == 'default' else self.current_spec['elements'][text])
        pass

    def changed_code(self):
        if self.code_selector.currentText() == '- delete -':
            if self.element_selector.currentText() == 'default':
                self.code_selector.setCurrentText(self.current_spec['default'])
            else:
                print('delete elementRange', self.element_selector.currentText())
        else:
            if self.element_selector.currentText() == 'default':
                self.current_spec['default'] = self.code_selector.currentText()
            else:
                self.current_spec['elements'][self.element_selector.currentText()] = self.code_selector.currentText()
            print('about to call changed_action with',self.current_spec)
            self.changed_action(self.current_spec)
