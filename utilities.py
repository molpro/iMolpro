import os
import json
from collections.abc import MutableMapping

from PyQt5.Qt import Qt
from PyQt5.QtCore import QTimer, QPoint, QCoreApplication
from PyQt5.QtGui import QFont, QFontDatabase, QTextCursor, QCursor
from PyQt5.QtWidgets import QPlainTextEdit, QMessageBox, QLabel, QMainWindow

from enum import Enum

from MenuBar import MenuBar


class VimMode(Enum):
    normal = 1
    insert = 2
    visual = 3
    commandline = 4
    replace = 5
    binary = 6
    org = 7


class QVimPlainTextEdit(QPlainTextEdit):
    def __init__(self, initial_mode=VimMode.normal):
        super().__init__()
        self.vimMode = initial_mode
        self.lastKey = None
        self.searching = False
        self.shiftKey = False
        self.searchReverse = False
        self.lastSearch = ''

        self.statusLine = QLabel(self)

    def keyPressEvent(self, e):
        # print('key', e.key(), self.vimMode, Qt.Key_Enter, Qt.Key_Return)
        if self.searching:
            if e.key() == Qt.Key_Enter or e.key() == Qt.Key_Return:
                self.search_and_move(self.statusLine.text()[1:], self.searchReverse)
                self.searching = False
                self.statusLine.hide()
            else:
                self.statusLine.setText(self.statusLine.text() + e.text())
                self.statusLine.show()
        elif self.vimMode == VimMode.insert:
            if e.key() == Qt.Key_Escape:
                self.enterMode(VimMode.normal)
            else:
                super().keyPressEvent(e)
        elif self.vimMode == VimMode.normal:
            if e.key() == Qt.Key_A:
                if self.shiftKey:
                    self.moveCursor(QTextCursor.EndOfLine)
                else:
                    self.moveCursor(QTextCursor.Right)
                self.enterMode(VimMode.insert)
            elif e.key() == Qt.Key_B:
                self.moveCursor(QTextCursor.StartOfWord)
            elif e.key() == Qt.Key_D and self.lastKey == Qt.Key_D:
                print('delete line not implemented')
            elif e.key() == Qt.Key_E:
                self.moveCursor(QTextCursor.EndOfWord)
            elif e.key() == Qt.Key_I:
                if self.shiftKey:
                    self.moveCursor(QTextCursor.StartOfLine)
                self.enterMode(VimMode.insert)
            if e.key() == Qt.Key_H:
                self.moveCursor(QTextCursor.Left)
            elif e.key() == Qt.Key_J:
                self.moveCursor(QTextCursor.Down)
            elif e.key() == Qt.Key_K:
                self.moveCursor(QTextCursor.Up)
            elif e.key() == Qt.Key_L:
                self.moveCursor(QTextCursor.Right)
            elif e.key() == Qt.Key_N:
                self.search_and_move(reverse=not self.searchReverse if self.shiftKey else self.searchReverse)
            elif e.key() == Qt.Key_O:
                if not self.shiftKey:
                    self.moveCursor(QTextCursor.Down)
                self.moveCursor(QTextCursor.StartOfLine)
                pos = self.textCursor().position()
                self.setPlainText(self.toPlainText()[:pos] + '\n' + self.toPlainText()[pos:])
                cursor = self.textCursor()
                cursor.setPosition(pos)
                self.setTextCursor(cursor)
                self.enterMode(VimMode.insert)
            elif e.key() == Qt.Key_R:
                print('replace not implemented')
            elif e.key() == Qt.Key_U:
                print('undo not implemented')
            elif e.key() == Qt.Key_V:
                print('visual mode not implemented')
            elif e.key() == Qt.Key_X:
                pos = self.textCursor().position()
                self.setPlainText(self.toPlainText()[:pos] + self.toPlainText()[pos + 1:])
                cursor = self.textCursor()
                cursor.setPosition(pos)
                self.setTextCursor(cursor)
            elif e.key() == Qt.Key_0:
                self.moveCursor(QTextCursor.StartOfLine)
            elif e.key() == Qt.Key_Dollar:
                self.moveCursor(QTextCursor.EndOfLine)
            elif e.key() == Qt.Key_Colon:
                print('command-line mode not implemented')
            elif e.key() == Qt.Key_Slash or e.key() == Qt.Key_Question:
                self.searchReverse = e.key() == Qt.Key_Question
                self.searching = True
                self.establishStatus(e.text())
            elif e.key() == Qt.Key_Shift:
                self.shiftKey = True
        self.lastKey = e.key()

    def establishStatus(self, message=''):
        self.statusLine.setFixedWidth(self.width())
        if message:
            self.statusLine.setText(message)
        self.statusLine.move(self.geometry().bottomLeft() - self.geometry().topLeft() + QPoint(6, -16)
                             )
        self.statusLine.raise_()
        self.lower()
        self.statusLine.show()

    def enterMode(self, mode: VimMode):
        self.vimMode = mode
        if mode == VimMode.insert:
            self.establishStatus('-- INSERT --')
        elif mode == VimMode.replace:
            self.establishStatus('-- REPLACE --')
        elif mode == VimMode.visual:
            self.establishStatus('-- VISUAL --')
        elif mode == VimMode.commandline:
            self.establishStatus(':')
        elif mode == VimMode.normal:
            self.statusLine.hide()

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Shift:
            # print('shift off')
            self.shiftKey = False

    def search_and_move(self, search_string=None, reverse=False):
        if search_string:
            self.lastSearch = search_string
        # print('searching for', self.lastSearch, self.textCursor().position())
        if reverse:
            newpos = self.toPlainText().rfind(self.lastSearch, 0, self.textCursor().position())
        else:
            newpos = self.toPlainText().find(self.lastSearch, self.textCursor().position() + 1)
        if newpos >= 0:
            # print('found', newpos, self.toPlainText()[newpos])
            cursor = self.textCursor()
            cursor.setPosition(newpos)
            self.setTextCursor(cursor)
            return True
        else:
            # print('not found')
            return False

    def resizeEvent(self, e):
        self.establishStatus()
        super().resizeEvent(e)


class EditFile(QVimPlainTextEdit):
    def __init__(self, filename: str, latency=1000):
        super().__init__(VimMode.insert)
        self.fileTime = None
        self.filename = str(filename)
        if os.path.isfile(self.filename):
            self.load()
        else:
            self.savedText = '\n'
        self.setPlainText(self.savedText)
        f = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        f.setPointSize(12)
        self.setFont(f)
        self.sync()

        self.flushTimer = QTimer()
        self.flushTimer.timeout.connect(self.sync)
        self.flushTimer.start(latency)

    def load(self):
        with open(self.filename, 'r') as f:
            self.savedText = f.read()
        if not self.savedText or self.savedText[-1] != '\n': self.savedText += '\n'
        super().setPlainText(self.savedText)
        self.fileTime = os.path.getmtime(self.filename)

    def sync(self):
        from time import time
        if os.path.isfile(self.filename) and (not self.fileTime or self.fileTime < os.path.getmtime(self.filename)):
            self.load()
        current = self.toPlainText()
        if not current or current[-1] != '\n':
            current += '\n'
            cursor = self.textCursor()
            super().setPlainText(current)
            self.setTextCursor(cursor)
            self.moveCursor(QTextCursor.Left)
        if current != self.savedText:
            with open(self.filename, 'w') as f:
                f.write(current)
            self.savedText = current
            self.fileTime = os.path.getmtime(self.filename)

    def setPlainText(self, text):
        super().setPlainText(text)
        self.sync()


class MainEditFile(QMainWindow):
    def __init__(self, filename: str, latency=1000):
        super().__init__()
        self.w = EditFile(filename, latency)
        self.setCentralWidget(self.w)
        self.setWindowTitle(str(filename))
        menubar = MenuBar(self)
        self.setMenuBar(menubar)
        menubar.addAction('Close', 'File', self.close, 'Ctrl+W')
        menubar.addAction('Quit', 'File', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')
        menubar.addAction('Cut', 'Edit', self.w.cut, 'Ctrl+X', 'Cut')
        menubar.addAction('Copy', 'Edit', self.w.copy, 'Ctrl+C', 'Copy')
        menubar.addAction('Paste', 'Edit', self.w.paste, 'Ctrl+X', 'Paste')
        menubar.addAction('Undo', 'Edit', self.w.undo, 'Ctrl+Z', 'Undo')
        menubar.addAction('Redo', 'Edit', self.w.redo, 'Shift+Ctrl+Z', 'Redo')
        menubar.addAction('Select All', 'Edit', self.w.selectAll, 'Ctrl+A', 'Redo')
        menubar.addSeparator('Edit')
        menubar.addAction('Zoom In', 'Edit', self.w.zoomIn, 'Shift+Ctrl+=', 'Increase font size')
        menubar.addAction('Zoom Out', 'Edit', self.w.zoomOut, 'Ctrl+-', 'Decrease font size')


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
        scrollbar_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 1)
        scrollbar_prev_value = scrollbar.value()
        if os.path.isfile(self.filename):
            if os.path.getmtime(self.filename) > self.modtime:
                self.modtime = os.path.getmtime(self.filename)
                with open(self.filename, 'r') as f:
                    self.setPlainText(f.read())
            if scrollbar_at_bottom:
                self.verticalScrollBar().setValue(scrollbar.maximum())
            else:
                self.verticalScrollBar().setValue(scrollbar_prev_value)

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


    def __str__(self):
        return 'OrbitalSet ' + str(type(self)) + '\n' + str(self.orbitals) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)

    @property
    def energies(self):
        return [orbital['energy'] for orbital in self.orbitals]


def factory_orbital_set(input: str, file_type=None, instance=-1):
    implementors = {
        'xml': OrbitalSetXML,
        'molden': OrbitalSetMolden,
    }
    if not file_type:
        import os
        base, suffix = os.path.splitext(input)
        return implementors[suffix[1:]](open(input, 'r').read(), instance)
    else:
        return implementors[file_type](input, instance)


class OrbitalSetMolden(OrbitalSet):
    def __init__(self, content: str, instance=-1):
        import re
        self.coordinateSet = 2
        super().__init__()
        self.orbitals = []
        vibact = False
        for line in content.split('\n'):
            if line.strip() == '[MO]':
                vibact = True
            elif vibact and line.strip() and line.strip()[0] == '[':
                vibact = False
            elif vibact and line.strip()[:3] == 'Ene':
                self.orbitals.append({'energy': float(re.sub(' +', ' ', line.strip()).split(' ')[1])})


class OrbitalSetXML(OrbitalSet):
    def __init__(self, content: str, instance=-1):
        super().__init__()
        import lxml
        root = lxml.etree.fromstring(content)
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        orbitals_node = root.xpath('//molpro-output:orbitals',
                                  namespaces=namespaces_)
        if -len(orbitals_node) > instance or len(orbitals_node) <= instance:
            raise IndexError('instance in OrbitalSet')
        self.coordinateSet = 0 + len(
            orbitals_node[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
                                         namespaces=namespaces_))
        xpath = orbitals_node[instance].xpath('molpro-output:orbital', namespaces=namespaces_)
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

    def __str__(self):
        return 'VibrationSet ' + str(type(self)) + '\n' + str(self.modes) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)

    @property
    def frequencies(self):
        return [mode['wavenumber'] for mode in self.modes]

    @property
    def wavenumbers(self):
        return [mode['wavenumber'] for mode in self.modes]


def factory_vibration_set(input: str, file_type=None, instance=-1):
    implementors = {
        'xml': VibrationSetXML,
        'molden': VibrationSetMolden,
    }
    if not file_type:
        import os
        base, suffix = os.path.splitext(input)
        return implementors[suffix[1:]](open(input, 'r').read(), instance)
    else:
        return implementors[file_type](input, instance)


class VibrationSetMolden(VibrationSet):
    def __init__(self, content: str, instance=-1):
        self.coordinateSet = 2
        super().__init__()
        self.modes = []
        vibact = False
        for line in content.split('\n'):
            if line.strip() == '[FREQ]':
                vibact = True
            elif vibact and line.strip() and line.strip()[0] == '[':
                vibact = False
            elif vibact and float(line.strip()) != 0.0:
                self.modes.append({'wavenumber': float(line.strip())})
            elif vibact:
                self.coordinateSet += 1


class VibrationSetXML(VibrationSet):
    def __init__(self, content: str, instance=-1):
        super().__init__()
        import lxml
        root = lxml.etree.fromstring(content)
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        vibrations_node = root.xpath('//molpro-output:vibrations',
                                    namespaces=namespaces_)
        if -len(vibrations_node) > instance or len(vibrations_node) <= instance:
            raise IndexError('instance in VibrationSet')
        self.coordinateSet = 1 + len(
            vibrations_node[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
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
            for c in (vibrations_node[instance].xpath(
                'molpro-output:normalCoordinate[not(@real_zero_imag) or @real_zero_imag!="Z"]',
                namespaces=namespaces_))
        ]


class FileBackedDictionary(MutableMapping):
    def __init__(self, filename: str):
        self.filename = filename
        self.filetime = 0.0
        self.refresh()

    def refresh(self):
        if os.path.exists(self.filename) and self.filetime < os.path.getmtime(self.filename):
            with open(self.filename, 'r') as fp:
                self.data = json.load(fp)
        else:
            self.data = {}

    def save(self):
        if not os.path.isdir(os.path.dirname(self.filename)):
            os.makedirs(os.path.dirname(self.filename))
        with open(self.filename, 'w') as fp:
            json.dump(self.data, fp)

    def __getitem__(self, item):
        self.refresh()
        return self.data[item]

    def __delitem__(self, item):
        self.refresh()
        del self.data[item]
        self.save()

    def __setitem__(self, key, value):
        self.refresh()
        self.data[key] = value
        self.save()

    def __iter__(self):
        self.refresh()
        return iter(self.data)

    def __len__(self):
        self.refresh()
        return len(self.data)

    def __repr__(self):
        return f"{type(self).__name__}({self.data})"
