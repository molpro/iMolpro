import sys

from PyQt5.QtWidgets import QComboBox, QVBoxLayout
from PyQt5.QtCore import pyqtSignal


class SpinComboBox(QComboBox):
    labels = ['Singlet', 'Doublet', 'Triplet', 'Quartet', 'Quintet', 'Sextet', 'Septet', 'Octet']
    spin_changed = pyqtSignal('int')

    def __init__(self, parent=None, initial_spin_2=None, maximum_spin_2=None, other_label='Other', auto_label='Automatic'):
        super().__init__(parent)
        self.other_label = other_label
        self.auto_label = auto_label
        self.labels = SpinComboBox.labels
        for _spin_2 in range(len(SpinComboBox.labels), maximum_spin_2 + 1):
            if _spin_2 % 2 == 1:
                self.labels.append('S=' + str(_spin_2) + '/2')
            else:
                self.labels.append('S=' + str(_spin_2 // 2))
        # if initial_spin_2 is not None:
        self.refresh(initial_spin_2)

    def refresh(self, initial_spin_2: int):
        r"""

        :param initial_spin_2:  If negative, used to get even/odd electron count, but then auto
        :type initial_spin_2: int
        :return:
        :rtype:
        """
        self.initialising = True
        self.clear()
        self.addItem(self.auto_label)
        self.addItems([self.labels[k] for k in range(initial_spin_2 % 2, len(self.labels), 2)])
        self.addItem(self.other_label)
        if initial_spin_2 >=0:
            self.setCurrentText(self.labels[initial_spin_2] if initial_spin_2 < len(self.labels) else self.other_label)
        else:
            self.setCurrentText(self.auto_label)
        self.currentTextChanged.connect(self.on_text_changed)
        self.initialising = False

    def on_text_changed(self, text):
        if self.initialising: return
        self.spin_changed.emit(self.labels.index(text) if text in self.labels and text else -1)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QWidget


    def on_spin_changed(ms2):
        print('new spin', ms2)


    app = QApplication(sys.argv)
    widget = QWidget()
    initial_spin_2 = 0
    boxes=[]
    layout=QVBoxLayout(widget)
    for initial_spin_2 in [-2,-1,0,1,2]:
        boxes.append(SpinComboBox(widget, initial_spin_2, maximum_spin_2=14))
        boxes[-1].spin_changed.connect(on_spin_changed)
        layout.addWidget(boxes[-1])

    widget.show()
    sys.exit(app.exec_())
