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


class VibrationSet:
    r"""
    Container for a set of molecular normal coordinates
    """

    def __init__(self, content: str, instance=-1):
        pass

    def __str__(self):
        return 'VibrationSet ' + str(type(self)) + '\n' + str(self.modes) + str('\n\nfirstCoordinateSet: ') + str(
            self.firstCoordinateSet)

    @property
    def frequencies(self):
        return [mode['wavenumber'] for mode in self.modes]

    @property
    def wavenumbers(self):
        return [mode['wavenumber'] for mode in self.modes]


def factoryVibrationSet(input: str, fileType=None, instance=-1):
    implementors = {
        'xml': VibrationSetXML,
        'molden': VibrationSetMolden,
    }
    if not fileType:
        import os
        base, suffix = os.path.splitext(input)
        return implementors[suffix[1:]](open(input, 'r').read(), instance)
    else:
        return implementors[fileType](input, instance)


class VibrationSetMolden(VibrationSet):
    def __init__(self, content: str, instance=-1):
        self.firstCoordinateSet = 2
        super().__init__(content, instance)
        self.modes = []
        vibact = False
        for line in content.split('\n'):
            if line.strip() == '[FREQ]':
                vibact = True
                vibrations = True
            elif vibact and line.strip() and line.strip()[0] == '[':
                vibact = False
            elif vibact and float(line.strip()) != 0.0:
                self.modes.append({'wavenumber': float(line.strip())})
            elif vibact:
                self.firstCoordinateSet += 1


class VibrationSetXML(VibrationSet):
    def __init__(self, content: str, instance=-1):
        super().__init__(content, instance)
        import lxml
        root = lxml.etree.fromstring(content)
        import pymolpro # TODO remove dependency
        vib = pymolpro.xpath(root, '//vibrations')
        if -len(vib) > instance or len(vib) <= instance:
            raise IndexError('instance in VibrationSet')
        self.firstCoordinateSet = 1 + len(
            vib[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
                                namespaces={'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                                            'xsd': 'http://www.w3.org/1999/XMLSchema',
                                            'cml': 'http://www.xml-cml.org/schema',
                                            'stm': 'http://www.xml-cml.org/schema',
                                            'xhtml': 'http://www.w3.org/1999/xhtml'}))
        coordinates = vib[instance].xpath(
            'molpro-output:normalCoordinate[not(@real_zero_imag) or @real_zero_imag!="Z"]',
            namespaces={'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                        'xsd': 'http://www.w3.org/1999/XMLSchema',
                        'cml': 'http://www.xml-cml.org/schema', 'stm': 'http://www.xml-cml.org/schema',
                        'xhtml': 'http://www.w3.org/1999/xhtml'})
        self.modes = [
            {
                'vector': [float(v) for v in c.text.split()],
                'wavenumber': float(c.attrib['wavenumber']),
                'units': c.attrib['units'],
                'IRintensity': float(c.attrib['IRintensity']),
                'IRintensityunits': c.attrib['IRintensityunits'],
                'symmetry': c.attrib['symmetry'],
                'real_zero_imag': c.attrib['real_zero_imag'],
            }
            for c in coordinates
        ]
