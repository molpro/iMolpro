import webbrowser
from typing import Dict, List, Optional, Any

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QComboBox, QLabel, QDialogButtonBox,
    QTableWidgetItem, QLineEdit, QPushButton, QHeaderView
)


class OptionsDialog(QDialog):
    """
    Dialog for editing options/settings with add/remove functionality.
    """
    prompt_text = '- Select option -'

    def __init__(
        self,
        current_options: Dict[str, Any],
        available_options: List[str],
        title: Optional[str] = None,
        parent=None,
        help_uri: Optional[str] = None,
        width: int = 500
    ):
        super().__init__(parent)
        if title:
            self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self._init_ui(current_options, available_options, help_uri)

    def _init_ui(self, current_options: Dict[str, Any], available_options: List[str], help_uri: Optional[str]):
        layout = QVBoxLayout(self)
        self.current = QTableWidget(self)
        self.current.setColumnCount(2)
        self.current.setHorizontalHeaderLabels(['Value', ''])
        self.current.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.current.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.current.verticalHeader().setVisible(True)
        self.remove_buttons = []
        for k, v in current_options.items():
            self.add(k, v)
        layout.addWidget(self.current)

        self.available_options = {opt: None for opt in available_options if opt not in current_options}
        if self.available_options:
            self.available = QComboBox(self)
            self.available.addItem(self.prompt_text)
            self.available.addItems(self.available_options)
            self.available.currentTextChanged.connect(self.add_from_registry)
            layout.addWidget(QLabel('Add entry:'))
            layout.addWidget(self.available)

        buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        if help_uri:
            doc_button = buttonbox.addButton('Documentation', QDialogButtonBox.HelpRole)
            doc_button.clicked.connect(lambda: webbrowser.open(help_uri))
        layout.addWidget(buttonbox)

    def add(self, key: str, value: Any):
        row = self.current.rowCount()
        self.current.setRowCount(row + 1)
        self.current.setVerticalHeaderItem(row, QTableWidgetItem(key))
        self.current.setCellWidget(row, 0, QLineEdit(str(value)))
        remove_btn = QPushButton('Remove')
        self.remove_buttons.append(remove_btn)
        self.current.setCellWidget(row, 1, remove_btn)
        remove_btn.clicked.connect(lambda _, k=key: self.remove(k))
        self.current.setCurrentCell(row, 0)

    def add_from_registry(self):
        key = self.available.currentText()
        if key == self.prompt_text or key not in self.available_options:
            return
        for row in range(self.current.rowCount()):
            if key == self.current.verticalHeaderItem(row).text():
                return
        self.add(key, self.available_options[key])
        self.available.setCurrentText(self.prompt_text)

    def remove(self, key: str):
        for row in range(self.current.rowCount()):
            if key == self.current.verticalHeaderItem(row).text():
                self.current.removeRow(row)
                return

    def exec(self) -> Optional[Dict[str, str]]:
        result = super().exec()
        if result == QDialog.Accepted:
            return {
                self.current.verticalHeaderItem(row).text(): self.current.cellWidget(row, 0).text()
                for row in range(self.current.rowCount())
            }
        return None
