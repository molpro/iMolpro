import webbrowser

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QComboBox, QLabel, QDialogButtonBox, QTableWidgetItem, \
    QLineEdit, QPushButton, QHeaderView


class OptionsDialog(QDialog):
    def __init__(self, current_options: dict, available_options: list, title=None, parent=None, help_uri=None,
                 width=500):
        super().__init__(parent)
        if title is not None:
            self.setWindowTitle(title)
        layout = QVBoxLayout(self)

        self.current = QTableWidget(self)
        self.current.setMinimumWidth(width)
        self.current.setColumnCount(2)
        self.current.setHorizontalHeaderLabels(['Value'])
        self.current.horizontalHeader().setVisible(False)
        self.remove_buttons = []
        for k, v in current_options.items():
            self.add(k, v)
        layout.addWidget(self.current)

        available_options_ = [available_option for available_option in available_options if
                              available_option not in current_options]
        if available_options_:
            self.available = QComboBox(self)
            self.available.addItem('')
            self.available.addItems(available_options_)
            self.available.currentTextChanged.connect(self.add_from_registry)
            layout.addWidget(QLabel('Add entry:'))
            layout.addWidget(self.available)

        buttonbox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # | QDialogButtonBox.Help if help_uri is not None else 0)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        if help_uri is not None:
            buttonbox.addButton('Documentation', QDialogButtonBox.HelpRole)
            buttonbox.helpRequested.connect(lambda help_uri=help_uri: webbrowser.open(help_uri))
        layout.addWidget(buttonbox)

    def add(self, key, value):
        row = self.current.rowCount()
        self.current.setRowCount(row + 1)
        self.current.setVerticalHeaderItem(row, QTableWidgetItem(key))
        self.current.setCellWidget(row, 0, QLineEdit(str(value)))
        self.remove_buttons.append(QPushButton('Remove'))
        self.current.setCellWidget(row, 1, self.remove_buttons[-1])
        self.remove_buttons[-1].clicked.connect(lambda arg, key=key: self.remove(key))
        self.current.setCurrentCell(row, 0)
        self.current.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.current.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def add_from_registry(self):
        key = self.available.currentText()
        if key == '': return
        for row in range(self.current.rowCount()):
            if key == self.current.verticalHeaderItem(row).text():
                return
        self.add(key, '')
        self.available.setCurrentText('')

    def remove(self, key):
        for row in range(self.current.rowCount()):
            if key == self.current.verticalHeaderItem(row).text():
                self.current.removeRow(row)
                return

    def exec(self):
        result = super().exec()
        if result == QDialog.Accepted:
            return {self.current.verticalHeaderItem(row).text(): self.current.cellWidget(row, 0).text() for row in
                    range(self.current.rowCount())}
