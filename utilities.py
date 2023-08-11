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
            self.load()
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

    def load(self):
        with open(self.filename, 'r') as f:
            self.savedText = f.read()
        if not self.savedText or self.savedText[-1] != '\n': self.savedText += '\n'
        self.setPlainText(self.savedText)
        self.fileTime = os.path.getmtime(self.filename)

    def flush(self):
        if self.fileTime and self.fileTime < os.path.getmtime(self.filename):
            self.load()
        current = self.toPlainText()
        if not current or current[-1] != '\n':
            current += '\n'
            self.setPlainText(current)
        if current != self.savedText:
            with open(self.filename, 'w') as f:
                f.write(current)
            self.savedText = current
            self.fileTime = os.path.getmtime(self.filename)

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


class OrbitalSet:
    r"""
    Container for a set of molecular orbitals
    """

    def __init__(self, content: str, instance=-1):
        pass

    def __str__(self):
        return 'OrbitalSet ' + str(type(self)) + '\n' + str(self.orbitals) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)

    @property
    def energies(self):
        return [orbital['energy'] for orbital in self.orbitals]


def factoryOrbitalSet(input: str, fileType=None, instance=-1):
    implementors = {
        'xml': OrbitalSetXML,
        'molden': OrbitalSetMolden,
    }
    if not fileType:
        import os
        base, suffix = os.path.splitext(input)
        return implementors[suffix[1:]](open(input, 'r').read(), instance)
    else:
        return implementors[fileType](input, instance)


class OrbitalSetMolden(OrbitalSet):
    def __init__(self, content: str, instance=-1):
        print('OrbitalSetMolden')
        import re
        self.coordinateSet = 2
        super().__init__(content, instance)
        self.orbitals = []
        vibact = False
        for line in content.split('\n'):
            if line.strip() == '[MO]':
                print('found [MO]')
                vibact = True
            elif vibact and line.strip() and line.strip()[0] == '[':
                vibact = False
            elif vibact and line.strip()[:3] == 'Ene':
                self.orbitals.append({'energy': float(re.sub(' +', ' ', line.strip()).split(' ')[1])})


class OrbitalSetXML(OrbitalSet):
    def __init__(self, content: str, instance=-1):
        super().__init__(content, instance)
        import lxml
        root = lxml.etree.fromstring(content)
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        orbitalsNode = root.xpath('//molpro-output:orbitals',
                                  namespaces=namespaces_)
        if -len(orbitalsNode) > instance or len(orbitalsNode) <= instance:
            raise IndexError('instance in OrbitalSet')
        self.coordinateSet = 0 + len(
            orbitalsNode[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
                                         namespaces=namespaces_))
        xpath = orbitalsNode[instance].xpath('molpro-output:orbital', namespaces=namespaces_)
        self.orbitals = [
            {
                'vector': [float(v) for v in c.text.split()],
                'energy': float(c.attrib['energy']),
                'ID': c.attrib['ID'],
                'symmetryID': c.attrib['symmetryID'],
            }
            for c in xpath
        ]


class VibrationSet:
    r"""
    Container for a set of molecular normal coordinates
    """

    def __init__(self, content: str, instance=-1):
        pass

    def __str__(self):
        return 'VibrationSet ' + str(type(self)) + '\n' + str(self.modes) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)

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
        self.coordinateSet = 2
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
                self.coordinateSet += 1


class VibrationSetXML(VibrationSet):
    def __init__(self, content: str, instance=-1):
        super().__init__(content, instance)
        import lxml
        root = lxml.etree.fromstring(content)
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        vibrationsNode = root.xpath('//molpro-output:vibrations',
                                    namespaces=namespaces_)
        if -len(vibrationsNode) > instance or len(vibrationsNode) <= instance:
            raise IndexError('instance in VibrationSet')
        self.coordinateSet = 1 + len(
            vibrationsNode[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
                                           namespaces=namespaces_))
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
            for c in (vibrationsNode[instance].xpath(
                'molpro-output:normalCoordinate[not(@real_zero_imag) or @real_zero_imag!="Z"]',
                namespaces=namespaces_))
        ]
