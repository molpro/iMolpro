from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QLabel, QWidget


class Chooser(QMainWindow):
    def __init__(self):
        super().__init__()

        self.layout = QHBoxLayout()
        temp = QLabel('Chooser')
        self.layout.addWidget(temp)
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)
