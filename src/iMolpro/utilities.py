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

try:
    KeyboardModifier = Qt.KeyboardModifier
except:
    KeyboardModifier = Qt

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
    # motions with no special linewise/charwise handling: usable standalone or as an operator's range
    _motions = {
        Key.Key_H: QTextCursor.Left,
        Key.Key_J: QTextCursor.Down,
        Key.Key_K: QTextCursor.Up,
        Key.Key_L: QTextCursor.Right,
        Key.Key_W: QTextCursor.NextWord,
        Key.Key_B: QTextCursor.PreviousWord,
        Key.Key_E: QTextCursor.EndOfWord,
    }

    def __init__(self, initial_mode=VimMode.normal):
        super().__init__()
        self.vimMode = initial_mode
        self.lastKey = None
        self.searching = False
        self.searchReverse = False
        self.lastSearch = ''
        self.countBuffer = ''
        self.pendingOperator = None
        self.operatorCount = 1
        self.pendingReplace = False
        self.pendingCharMotion = None
        self.charMotionTotal = 1

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
            shift = bool(e.modifiers() & KeyboardModifier.ShiftModifier)
            self.handleNormalKey(e, shift)
        self.lastKey = e.key()

    def handleNormalKey(self, e, shift):
        key = e.key()

        # modifier-only presses arrive as their own event, ahead of the letter they're
        # held for (e.g. Shift before '$') - ignore them rather than cancelling state
        if key in (Key.Key_Shift, Key.Key_Control, Key.Key_Alt, Key.Key_Meta):
            return

        if self.pendingReplace:
            self.pendingReplace = False
            self.statusLine.hide()
            if e.text():
                cursor = self.textCursor()
                cursor.deleteChar()
                cursor.insertText(e.text())
                cursor.movePosition(QTextCursor.Left)
                self.setTextCursor(cursor)
            return

        if self.pendingCharMotion:
            motion_type = self.pendingCharMotion
            total = self.charMotionTotal
            self.pendingCharMotion = None
            self.statusLine.hide()
            if e.text():
                self.applyCharMotion(motion_type, e.text(), total)
            self.pendingOperator = None
            return

        if key == Key.Key_Escape:
            self.countBuffer = ''
            self.pendingOperator = None
            self.statusLine.hide()
            return

        # counts: leading digits accumulate; a bare '0' (no count yet) is the "start of line" motion
        if Key.Key_0 <= key <= Key.Key_9 and e.text().isdigit():
            if e.text() == '0' and not self.countBuffer:
                self.moveCursor(QTextCursor.StartOfLine)
            else:
                self.countBuffer += e.text()
                self.establishStatus(('d' if self.pendingOperator else '') + self.countBuffer)
            return

        repeat = int(self.countBuffer) if self.countBuffer else 1
        self.countBuffer = ''

        if shift and key in (Key.Key_W, Key.Key_B, Key.Key_E):
            total = (self.operatorCount if self.pendingOperator else 1) * repeat
            self.applyWORDMotion(key, total)
            return

        motion = self._motions.get(key)
        if motion is not None:
            cursor = self.textCursor()
            if self.pendingOperator == 'd':
                self._moveByRepeated(cursor, motion, QTextCursor.KeepAnchor, self.operatorCount * repeat)
                cursor.removeSelectedText()
                self.pendingOperator = None
                self.statusLine.hide()
            else:
                self._moveByRepeated(cursor, motion, QTextCursor.MoveAnchor, repeat)
            self.setTextCursor(cursor)
            return

        if key == Key.Key_Dollar:
            cursor = self.textCursor()
            if self.pendingOperator == 'd':
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                self.pendingOperator = None
                self.statusLine.hide()
            else:
                cursor.movePosition(QTextCursor.EndOfLine)
            self.setTextCursor(cursor)
            return

        if key == Key.Key_D:
            if self.pendingOperator == 'd':
                self.deleteLines(self.operatorCount * repeat)
                self.pendingOperator = None
                self.statusLine.hide()
            else:
                self.pendingOperator = 'd'
                self.operatorCount = repeat
                self.establishStatus((str(repeat) if repeat != 1 else '') + 'd')
            return

        if key == Key.Key_F or key == Key.Key_T:
            self.pendingCharMotion = ('F' if shift else 'f') if key == Key.Key_F else ('T' if shift else 't')
            self.charMotionTotal = (self.operatorCount if self.pendingOperator else 1) * repeat
            prefix = 'd' if self.pendingOperator else ''
            count = str(repeat) if repeat != 1 else ''
            self.establishStatus(prefix + count + self.pendingCharMotion)
            return

        # any other key aborts a pending operator, same as real vim
        self.pendingOperator = None
        self.statusLine.hide()

        if key == Key.Key_A:
            self.moveCursor(QTextCursor.EndOfLine if shift else QTextCursor.Right)
            self.enterMode(VimMode.insert)
        elif key == Key.Key_I:
            if shift:
                self.moveCursor(QTextCursor.StartOfLine)
            self.enterMode(VimMode.insert)
        elif key == Key.Key_N:
            self.search_and_move(reverse=not self.searchReverse if shift else self.searchReverse)
        elif key == Key.Key_O:
            cursor = self.textCursor()
            if shift:
                cursor.movePosition(QTextCursor.StartOfBlock)
                cursor.insertBlock()
                cursor.movePosition(QTextCursor.PreviousBlock)
            else:
                cursor.movePosition(QTextCursor.EndOfBlock)
                cursor.insertBlock()
            self.setTextCursor(cursor)
            self.enterMode(VimMode.insert)
        elif key == Key.Key_R:
            self.pendingReplace = True
            self.establishStatus('r')
        elif key == Key.Key_U:
            for _ in range(repeat):
                self.undo()
        elif key == Key.Key_V:
            print('visual mode not implemented')
        elif key == Key.Key_X:
            cursor = self.textCursor()
            for _ in range(repeat):
                cursor.deleteChar()
            self.setTextCursor(cursor)
        elif key == Key.Key_Colon:
            print('command-line mode not implemented')
        elif key == Key.Key_Slash or key == Key.Key_Question:
            self.searchReverse = key == Key.Key_Question
            self.searching = True
            self.establishStatus(e.text())

    def deleteLines(self, count):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        start = cursor.position()
        moved = 0
        while moved < count and cursor.movePosition(QTextCursor.NextBlock):
            moved += 1
        if moved < count:
            cursor.movePosition(QTextCursor.End)
        end = cursor.position()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)

    def _moveByRepeated(self, cursor, motion, mode, count):
        """cursor.movePosition(motion, mode, count) is unreliable for EndOfWord: Qt treats a
        cursor already sitting at a word's end as a no-op rather than advancing to the next
        word's end, so repeating it n times can get stuck instead of covering n words."""
        if motion != QTextCursor.EndOfWord:
            cursor.movePosition(motion, mode, count)
            return
        for _ in range(count):
            before = cursor.position()
            cursor.movePosition(QTextCursor.EndOfWord, mode)
            if cursor.position() == before:
                cursor.movePosition(QTextCursor.NextWord, mode)
                cursor.movePosition(QTextCursor.EndOfWord, mode)

    def applyWORDMotion(self, key, count):
        """W/B/E: like w/b/e but a WORD is a maximal run of non-blank characters - blanks are
        the only separator, unlike w/b/e which also break on punctuation."""
        text = self.toPlainText()
        pos = self.textCursor().position()
        for _ in range(count):
            if key == Key.Key_W:
                pos = self._nextWORDStart(text, pos)
            elif key == Key.Key_B:
                pos = self._prevWORDStart(text, pos)
            else:  # Key_E
                pos = self._endOfWORDPos(text, pos)
        cursor = self.textCursor()
        if self.pendingOperator == 'd':
            origin = cursor.position()
            cursor.setPosition(min(origin, pos))
            cursor.setPosition(max(origin, pos), QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self.pendingOperator = None
            self.statusLine.hide()
        else:
            cursor.setPosition(pos)
        self.setTextCursor(cursor)

    @staticmethod
    def _nextWORDStart(text, pos):
        n = len(text)
        i = pos
        while i < n and not text[i].isspace():
            i += 1
        while i < n and text[i].isspace():
            i += 1
        return i

    @staticmethod
    def _prevWORDStart(text, pos):
        i = pos
        while i > 0 and text[i - 1].isspace():
            i -= 1
        while i > 0 and not text[i - 1].isspace():
            i -= 1
        return i

    @staticmethod
    def _endOfWORDPos(text, pos):
        n = len(text)
        if n == 0:
            return 0
        i = min(pos, n - 1)
        # already on the last character of a WORD: step past it (and the blanks after it)
        # before searching, so repeated E always advances instead of getting stuck
        if not text[i].isspace() and (i + 1 >= n or text[i + 1].isspace()):
            i += 1
        while i < n and text[i].isspace():
            i += 1
        while i + 1 < n and not text[i + 1].isspace():
            i += 1
        return min(i + 1, n)

    def applyCharMotion(self, motion_type, char, total):
        """f/t search forward, F/T search backward, on the current line only (as in vim).
        t/T land one character short of the match, on the near side of it."""
        cursor = self.textCursor()
        text = cursor.block().text()
        forward = motion_type in ('f', 't')
        idx = cursor.positionInBlock()
        for _ in range(total):
            idx = text.find(char, idx + 1) if forward else text.rfind(char, 0, idx)
            if idx == -1:
                return  # not found: motion (and any pending operator) does nothing, as in vim
        block_pos = cursor.block().position()
        if motion_type in ('f', 'F'):
            target = block_pos + idx
        elif motion_type == 't':
            target = block_pos + idx - 1
        else:  # 'T'
            target = block_pos + idx + 1
        # f/t are inclusive-forward, F/T inclusive-backward: the boundary always includes
        # whichever character the motion landed the cursor on
        boundary = target + 1 if forward else target
        if self.pendingOperator == 'd':
            origin = cursor.position()
            cursor.setPosition(min(origin, boundary))
            cursor.setPosition(max(origin, boundary), QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        else:
            cursor.setPosition(target)
        self.setTextCursor(cursor)

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
