import os
import pathlib

from pymolpro.defbas import periodic_table
import json
from collections.abc import MutableMapping
from typing import Any

import numpy

from .cube_data import CubeData

try:
    from PySide6.QtCore import QTimer, QPoint, QCoreApplication, Qt
    from PySide6.QtGui import QFont, QFontDatabase, QTextCursor, QCursor
    from PySide6.QtWidgets import QPlainTextEdit, QMessageBox, QLabel, QMainWindow
except ImportError:
    try:
        from PyQt6.QtCore import QTimer, QPoint, QCoreApplication, Qt
        from PyQt6.QtGui import QFont, QFontDatabase, QTextCursor, QCursor
        from PyQt6.QtWidgets import QPlainTextEdit, QMessageBox, QLabel, QMainWindow
    except ImportError:
        from PyQt5.QtCore import QTimer, QPoint, QCoreApplication, Qt
        from PyQt5.QtGui import QFont, QFontDatabase, QTextCursor, QCursor
        from PyQt5.QtWidgets import QPlainTextEdit, QMessageBox, QLabel, QMainWindow

try:
    FixedFont = QFontDatabase.FixedFont
except:
    FixedFont = QFontDatabase.SystemFont.FixedFont

try:
    Key = Qt.Key
except:
    Key = Qt

from enum import Enum

from .MenuBar import MenuBar


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
        # print('key', e.key(), self.vimMode, Key.Key_Enter, Key.Key_Return)
        if self.searching:
            if e.key() == Key.Key_Enter or e.key() == Key.Key_Return:
                self.search_and_move(self.statusLine.text()[1:], self.searchReverse)
                self.searching = False
                self.statusLine.hide()
            else:
                self.statusLine.setText(self.statusLine.text() + e.text())
                self.statusLine.show()
        elif self.vimMode == VimMode.insert:
            if e.key() == Key.Key_Escape:
                self.enterMode(VimMode.normal)
            else:
                super().keyPressEvent(e)
        elif self.vimMode == VimMode.normal:
            if e.key() == Key.Key_A:
                if self.shiftKey:
                    self.moveCursor(QTextCursor.EndOfLine)
                else:
                    self.moveCursor(QTextCursor.Right)
                self.enterMode(VimMode.insert)
            elif e.key() == Key.Key_B:
                self.moveCursor(QTextCursor.StartOfWord)
            elif e.key() == Key.Key_D and self.lastKey == Key.Key_D:
                print('delete line not implemented')
            elif e.key() == Key.Key_E:
                self.moveCursor(QTextCursor.EndOfWord)
            elif e.key() == Key.Key_I:
                if self.shiftKey:
                    self.moveCursor(QTextCursor.StartOfLine)
                self.enterMode(VimMode.insert)
            if e.key() == Key.Key_H:
                self.moveCursor(QTextCursor.Left)
            elif e.key() == Key.Key_J:
                self.moveCursor(QTextCursor.Down)
            elif e.key() == Key.Key_K:
                self.moveCursor(QTextCursor.Up)
            elif e.key() == Key.Key_L:
                self.moveCursor(QTextCursor.Right)
            elif e.key() == Key.Key_N:
                self.search_and_move(reverse=not self.searchReverse if self.shiftKey else self.searchReverse)
            elif e.key() == Key.Key_O:
                if not self.shiftKey:
                    self.moveCursor(QTextCursor.Down)
                self.moveCursor(QTextCursor.StartOfLine)
                pos = self.textCursor().position()
                self.setPlainText(self.toPlainText()[:pos] + '\n' + self.toPlainText()[pos:])
                cursor = self.textCursor()
                cursor.setPosition(pos)
                self.setTextCursor(cursor)
                self.enterMode(VimMode.insert)
            elif e.key() == Key.Key_R:
                print('replace not implemented')
            elif e.key() == Key.Key_U:
                print('undo not implemented')
            elif e.key() == Key.Key_V:
                print('visual mode not implemented')
            elif e.key() == Key.Key_X:
                pos = self.textCursor().position()
                self.setPlainText(self.toPlainText()[:pos] + self.toPlainText()[pos + 1:])
                cursor = self.textCursor()
                cursor.setPosition(pos)
                self.setTextCursor(cursor)
            elif e.key() == Key.Key_0:
                self.moveCursor(QTextCursor.StartOfLine)
            elif e.key() == Key.Key_Dollar:
                self.moveCursor(QTextCursor.EndOfLine)
            elif e.key() == Key.Key_Colon:
                print('command-line mode not implemented')
            elif e.key() == Key.Key_Slash or e.key() == Key.Key_Question:
                self.searchReverse = e.key() == Key.Key_Question
                self.searching = True
                self.establishStatus(e.text())
            elif e.key() == Key.Key_Shift:
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
        if e.key() == Key.Key_Shift:
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
        f = QFont(QFontDatabase.systemFont(FixedFont))
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
    def __init__(self, filename: str, latency=1000, point_size=10):
        super().__init__()
        self.setReadOnly(True)
        self.latency = latency
        f = QFont(QFontDatabase.systemFont(FixedFont))
        f.setPointSize(point_size)
        self.setFont(f)
        self.modtime = 0.0
        self.reset(filename)

    def refresh(self):
        scrollbar = self.verticalScrollBar()
        scrollbar_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 1)
        scrollbar_prev_value = scrollbar.value()
        if os.path.isfile(self.filename):
            modtime = os.path.getmtime(self.filename)
            if modtime > self.modtime:
                self.modtime = modtime
                with open(self.filename, 'r') as f:
                    contents = f.read()
                    self.clear()
                    self.setPlainText(contents)
                    contents = self.toPlainText()  # seems to be needed to ensure sync
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


class CoordinateSet:
    r"""
    Container for a set of molecular orbitals
    """

    def __str__(self):
        return 'CoordinateSet ' + str(type(self)) + '\n' + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)


def factory_coordinate_set(input: str, file_type=None, instance=-1):
    implementors = {
        'xml': CoordinateSetXML,
        'molden': CoordinateSetMolden,
    }
    if not file_type:
        import os
        base, suffix = os.path.splitext(input)
        return implementors[suffix[1:]](open(input, 'r').read(), instance)
    else:
        return implementors[file_type](input, instance)


class CoordinateSetMolden(CoordinateSet):
    def __init__(self, content: str, instance=-1):
        import re
        self.coordinateSet = 1
        super().__init__()


class CoordinateSetXML(CoordinateSet):
    def __init__(self, content: str, instance=-1):
        super().__init__()
        import lxml
        root = lxml.etree.fromstring(content)
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        coordinates_node = root.xpath('//cml:atomArray',
                                      namespaces=namespaces_)
        if -len(coordinates_node) > instance or len(coordinates_node) <= instance:
            raise IndexError('instance in CoordinateSet')
        self.coordinateSet = 0 + len(
            coordinates_node[instance].xpath('preceding::cml:atomArray | preceding::molpro-output:normalCoordinate',
                                             namespaces=namespaces_))


class OrbitalSet:
    r"""
    Container for a set of molecular orbitals
    """

    def __str__(self):
        return 'OrbitalSet ' + str(type(self)) + '\n' + str(self.orbitals) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet)

    @property
    def energies(self):
        return [orbital['energy'] if 'energy' in orbital else 0.0 for orbital in self.orbitals]


def factory_orbital_set(input: str, file_type=None, instance=-1):
    implementors = {
        # 'xml': OrbitalSetXML, # this needs a fix in jmol to work properly
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
        self.coordinateSet = 1
        super().__init__()
        self.orbitals = []
        mo_section = False
        for line in content.split('\n'):
            if line.strip() == '[MO]':
                mo_section = True
                mo_header = False
            elif mo_section and line.strip() and line.strip()[0] == '[':
                mo_section = False
            elif mo_section and not mo_header and re.match('.*=.*', line.strip()):
                mo_header = True
                self.orbitals.append({})
            elif mo_section and mo_header and not re.match('.*=.*', line.strip()):
                mo_header = False
            if mo_section and mo_header:
                value = re.sub('.*= *', '', line.strip())
                if re.match(' *Sym *=', line):
                    self.orbitals[-1]['ID'] = value
                elif re.match(' *Ene *=', line):
                    self.orbitals[-1]['energy'] = float(value)
                elif re.match(' *Occup *=', line):
                    self.orbitals[-1]['occupation'] = float(value)
                elif re.match(' *Spin *=', line):
                    self.orbitals[-1]['spin'] = value
        self.index = [list(numpy.argsort(self.energies)).index(i) + 1 for i in range(len(self.orbitals))]


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
                'occupation': float(c.attrib['occupation']),
            }
            for c in xpath
        ]
        self.index = [i + 1 for i in range(len(self.orbitals))]


class VibrationSet:
    r"""
    Container for a set of molecular normal coordinates
    """

    def __str__(self):
        return 'VibrationSet ' + str(type(self)) + '\n' + str(self.modes) + str('\n\ncoordinateSet: ') + str(
            self.coordinateSet) + str('\n\natoms: ') + str(self.atoms)

    @property
    def frequencies(self):
        return [mode['wavenumber'] for mode in self.modes]

    @property
    def wavenumbers(self):
        return [mode['wavenumber'] for mode in self.modes]


def displace_coordinate(source: list[dict] | CubeData, coordinate: list[float], displacement: float) -> list[dict]:
    if isinstance(source, CubeData):
        return displace_coordinate(source.atoms, coordinate, displacement)
    result = []
    for i, atom in enumerate(source):
        result.append({'atomic_number': atom['atomic_number'],
                       'xyz': [atom['xyz'][j] + displacement * coordinate[3 * i + j] for j in range(3)]})
    return result


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
        try:
            root = lxml.etree.fromstring(content)
        except:
            self.modes = []
            self.coordinateSet = 0
            return
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
        coords = vibrations_node[instance].xpath('preceding::cml:atomArray[1]', namespaces=namespaces_)
        self.atoms = []
        angstrom = 1.8897161646321
        for coord in coords[0]:
            self.atoms.append({'xyz': [angstrom * float(coord.attrib['x3']), angstrom * float(coord.attrib['y3']),
                                       angstrom * float(coord.attrib['z3'])],
                               'atomic_number': periodic_table.index(coord.attrib['elementType']) + 1})
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
                'molpro-output:normalCoordinate',
                namespaces=namespaces_))
        ]

    def __eq__(self, other):
        if not isinstance(other, VibrationSetXML):
            return False
        return self.modes == other.modes and self.coordinateSet == other.coordinateSet


class FileBackedDictionary(MutableMapping):
    #: Sentinel accepted by __setitem__ to mean "discard any stored value and fall back to the default"
    DEFAULT = object()

    def __init__(self, filename: str):
        self.filename = filename
        self.filetime = 0.0
        self.defaults = {}
        self.refresh()

    def add_default(self, key, value):
        self.defaults[key] = value

    def refresh(self):
        if os.path.exists(self.filename) and self.filetime < os.path.getmtime(self.filename) and os.stat(
                self.filename).st_size > 0:
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
        if item in self.data:
            return self.data[item]
        return self.defaults[item]

    def __delitem__(self, item):
        self.refresh()
        del self.data[item]
        self.save()

    def __setitem__(self, key, value):
        self.refresh()
        if value is FileBackedDictionary.DEFAULT:
            if key in self.data:
                del self.data[key]
                self.save()
        else:
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


def writable_directory(preferred: str = None) -> pathlib.Path:
    if preferred is not None and os.access(preferred, os.W_OK):
        return preferred
    tmpdir = pathlib.Path('/tmp')
    for env in ['TMPDIR', 'TMP', 'TEMP', 'SCRATCH', 'HOME', 'USERPROFILE']:
        if env in os.environ and os.access(os.environ[env], os.W_OK):
            tmpdir = pathlib.Path(os.environ[env])
            break
    return tmpdir


def atoms_from_xyz(initial_xyz: str) -> list[Any]:
    angstrom = 1.8897161646321
    with open(initial_xyz, 'r') as f:
        atoms = []
        f.readline()
        f.readline()
        while line := f.readline():
            linesplit = line.split()
            atom = {}
            atom['atomic_number'] = int(periodic_table.index(linesplit[0])) + 1
            atom['xyz'] = [float(x) * angstrom for x in linesplit[1:4]]
            atoms.append(atom)
    return atoms
