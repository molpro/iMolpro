import atexit
import os

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QPlainTextEdit, QMessageBox


class EditFile(QPlainTextEdit):
    def __init__(self, filename: str, latency=1000):
        super().__init__()
        self.filename = str(filename)
        if os.path.isfile(self.filename):
            with open(self.filename, 'r') as f:
                self.savedText = f.read()
            if not self.savedText or self.savedText[-1] != '\n': self.savedText += '\n'
        else:
            self.savedText = '\n'
        self.setPlainText(self.savedText)
        f = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        f.setPointSize(12)
        self.setFont(f)
        self.flush()

        import atexit
        atexit.register(self.flush)
        self.flushTimer = QTimer()
        self.flushTimer.timeout.connect(self.flush)
        self.flushTimer.start(latency)

    def flush(self):
        current = self.toPlainText()
        if not current or current[-1] != '\n':
            current += '\n'
            self.setPlainText(current)
        if current != self.savedText:
            with open(self.filename, 'w') as f:
                f.write(current)
            self.savedText = current

    def setPlainText(self, text):
        super().setPlainText(text)
        self.flush()

    def __del__(self):
        self.flush()
        atexit.unregister(self.flush)


class ViewFile(QPlainTextEdit):
    def __init__(self, filename: str, latency=1000):
        super().__init__()
        self.setReadOnly(True)
        self.latency = latency
        f = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        f.setPointSize(10)
        self.setFont(f)
        self.modtime = 0.0
        self.reset(filename)

    def refresh(self):
        scrollbar = self.verticalScrollBar()
        scrollbarAtBottom = scrollbar.value() >= (scrollbar.maximum() - 1)
        scrollbarPrevValue = scrollbar.value()
        if os.path.isfile(self.filename):
            if os.path.getmtime(self.filename) > self.modtime:
                self.modtime = os.path.getmtime(self.filename)
                with open(self.filename, 'r') as f:
                    self.setPlainText(f.read())
            if scrollbarAtBottom:
                self.verticalScrollBar().setValue(scrollbar.maximum())
            else:
                self.verticalScrollBar().setValue(scrollbarPrevValue)

    def reset(self, filename):
        self.filename = str(filename)
        self.savedText = ''
        self.refreshTimer = QTimer()
        self.refreshTimer.timeout.connect(self.refresh)
        self.refreshTimer.start(self.latency)


def force_suffix(filename, suffix='molpro'):
    if not filename:
        return ''
    fn = filename
    from pathlib import Path
    if not Path(fn).suffix: fn += '.' + suffix
    if Path(fn).suffix != '.' + suffix:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText('Invalid project file name: ' + fn + '\nThe suffix must be ".' + suffix + '"')
        msg.setWindowTitle('Error')
        msg.exec_()
        return ''
    return fn
