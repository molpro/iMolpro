import sys

from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import pyqtSignal


class SpinComboBox(QComboBox):
    labels = ['Singlet', 'Doublet', 'Triplet', 'Quartet', 'Quintet', 'Sextet', 'Septet', 'Octet']
    spin_changed = pyqtSignal('int')

    def __init__(self, parent=None, initial_spin_2=None, maximum_spin_2=None, other_label='Other'):
        super().__init__(parent)
        self.labels = SpinComboBox.labels
        for _spin_2 in range(len(SpinComboBox.labels), maximum_spin_2 + 1):
            if _spin_2 % 2 == 1:
                self.labels.append('S=' + str(_spin_2) + '/2')
            else:
                self.labels.append('S=' + str(_spin_2 // 2))
        self.other_label = other_label
        if initial_spin_2 is not None:
            self.refresh(initial_spin_2)

    def refresh(self, initial_spin_2: int):
        self.initialising = True
        self.clear()
        self.addItems([self.labels[k] for k in range(initial_spin_2 % 2, len(self.labels), 2)])
        self.addItem(self.other_label)
        self.setCurrentText(self.labels[initial_spin_2] if initial_spin_2 < len(self.labels) else self.other_label)
        self.currentTextChanged.connect(self.on_text_changed)
        self.initialising = False

    def on_text_changed(self, text):
        if self.initialising: return
        if text in self.labels:
            self.spin_changed.emit(self.labels.index(text))


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QWidget


    def on_spin_changed(ms2):
        print('new spin', ms2)


    app = QApplication(sys.argv)
    widget = QWidget()
    box = SpinComboBox(widget, 0, maximum_spin_2=14)
    box.spin_changed.connect(on_spin_changed)

    widget.show()
    sys.exit(app.exec_())
