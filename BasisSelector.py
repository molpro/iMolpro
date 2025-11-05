import copy
from typing import Callable, Optional, Dict, List, Any
from functools import partial
from utilities import mixed_core_correlation_only_valence

from PyQt5.QtWidgets import QComboBox, QWidget, QLabel, QInputDialog, QGridLayout, QPushButton


class BasisSelector(QWidget):
    """
    Widget for selecting basis sets.
    """
    new_elementRange = '- new element or range -'
    delete_elementRange = '- delete element or range -'

    def __init__(self, changed_action: Callable[[Dict[str, Any]], None], null_prompt: str):
        super().__init__()
        self.changed_action = changed_action
        self.null_prompt = null_prompt
        layout = QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.current_spec: Dict[str, Any] = {}
        self.possible_basis_sets: List[str] = []
        self.mixed_core_correlation = False

    def reload(self, current_spec: Optional[Dict[str, Any]] = None, possible_basis_sets: Optional[List[str]] = None, mixed_core_correlation: Optional[bool] = None):
        if mixed_core_correlation is not None:
            self.mixed_core_correlation = mixed_core_correlation
        if possible_basis_sets is not None:
            self.possible_basis_sets = possible_basis_sets
        if current_spec is not None:
            self.current_spec = copy.deepcopy(current_spec)

        # Remove all widgets from layout safely
        for i in reversed(range(self.layout().count())):
            item = self.layout().itemAt(i)
            widget = item.widget()
            if widget is not None:
                self.layout().removeWidget(widget)
                widget.setParent(None)

        # Default selector
        self.layout().addWidget(QLabel('Default'), 0, 0)
        default_selector = QComboBox(self)
        default_selector.clear()
        default_selector.addItems([self.null_prompt] + self.possible_basis_sets)
        select_ = self.current_spec.get('default', self.null_prompt)
        if select_ not in self.possible_basis_sets:
            select_ = self.null_prompt
        default_selector.setCurrentText(select_)
        default_selector.currentTextChanged.connect(partial(self.changed_code, default_selector, 'default'))
        self.layout().addWidget(default_selector, 0, 1)

        # Element selectors
        count = 1
        elements = self.current_spec.get('elements', {})
        for k, v in elements.items():
            self.layout().addWidget(QLabel(k), count, 0)
            code_selector = QComboBox(self)
            possible_basis_sets = [set for set in self.possible_basis_sets if mixed_core_correlation_only_valence(
                k) or self.mixed_core_correlation != 'mixed' or 'CV' not in set]
            code_selector.addItems([self.null_prompt] + possible_basis_sets + [self.delete_elementRange])
            select_ = v if v in possible_basis_sets else self.null_prompt
            code_selector.setCurrentText(select_)
            code_selector.currentTextChanged.connect(partial(self.changed_code, code_selector, k))
            self.layout().addWidget(code_selector, count, 1)
            count += 1

        # Add new element/range button
        new_element_button = QPushButton('Element or range')
        self.layout().addWidget(new_element_button, count, 0, 1, 2)
        new_element_button.clicked.connect(self.new_element)

    def new_element(self):
        range_str, ok = QInputDialog.getText(self, 'New element range',
                                             'Give chemical symbol of element, or a range such as Li-Ne')
        if ok and range_str:
            if 'elements' not in self.current_spec:
                self.current_spec['elements'] = {}
            self.current_spec['elements'][range_str] = self.current_spec.get('default', self.null_prompt)
            self.reload()

    def changed_code(self, selector: QComboBox, code: str):
        selected_text = selector.currentText()
        if selected_text == self.delete_elementRange:
            if 'elements' in self.current_spec and code in self.current_spec['elements']:
                self.current_spec['elements'].pop(code)
                self.changed_action(self.current_spec)
                self.reload()
        else:
            if code == 'default':
                self.current_spec['default'] = selected_text
            else:
                if 'elements' not in self.current_spec:
                    self.current_spec['elements'] = {}
                self.current_spec['elements'][code] = selected_text
            self.changed_action(self.current_spec)
