import os
import pathlib
import shutil
import sys
import re

from PyQt5.QtCore import QTimer, pyqtSignal, QUrl, QCoreApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QMessageBox, QMenuBar, QTabWidget, QAction, QFileDialog, QDialog, QDialogButtonBox
from pymolpro import Project

import molpro_input
from MenuBar import MenuBar
from help import HelpManager
from utilities import EditFile, ViewFile, factoryVibrationSet, factoryOrbitalSet, MainEditFile
from backend import configureBackend


class StatusBar(QLabel):
    def __init__(self, project: Project, runButton: QPushButton, killButton: QPushButton, latency=1000):
        super().__init__()
        self.project = project
        self.runButton = runButton
        self.killButton = killButton
        self.refreshTimer = QTimer()
        self.refreshTimer.timeout.connect(self.refresh)
        self.refreshTimer.start(latency)

    def refresh(self):
        self.setText('Status: ' + ('run ' + pathlib.Path(
            self.project.filename()).stem + ' ' if self.project.filename() != self.project.filename(
            run=-1) else '') + self.project.status)
        self.runButton.setDisabled(not self.project.run_needed())
        self.killButton.setDisabled(self.project.status != 'running' and self.project.status != 'waiting')


class ViewProjectOutput(ViewFile):
    def __init__(self, project, suffix='out', width=800, latency=100, fileNameLatency=2000):
        self.project = project
        self.suffix = suffix
        super().__init__(self.project.filename(suffix), latency=latency)
        super().setMinimumWidth(width)
        self.refreshOutputFileTimer = QTimer()
        self.refreshOutputFileTimer.timeout.connect(self.refreshOutputFile)
        self.refreshOutputFileTimer.start(fileNameLatency)  # find a better way

    def refreshOutputFile(self):
        latestFilename = self.project.filename(self.suffix)
        if latestFilename != self.filename:
            self.reset(latestFilename)


class ProjectWindow(QMainWindow):
    closeSignal = pyqtSignal(QWidget)
    newSignal = pyqtSignal(QWidget)
    chooserSignal = pyqtSignal(QWidget)

    def __init__(self, filename=None, latency=1000):
        super().__init__()

        assert filename is not None
        self.project = Project(filename)

        os.environ['PATH'] = os.popen(os.environ['SHELL'] + " -l -c 'echo $PATH'").read() + ':' + os.environ[
            'PATH']  # make PATH just as if running from shell
        self.JSmolMinJS = str(pathlib.Path(__file__).parent / "JSmol.min.js")
        if hasattr(sys, '_MEIPASS'):
            os.environ['QTWEBENGINEPROCESS_PATH'] = os.path.normpath(os.path.join(
                sys._MEIPASS, 'PyQt5', 'Qt', 'libexec', 'QtWebEngineProcess'
            ))
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox'
        likely_qtwebengineprocess = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PyQt5', 'Qt5', 'libexec', 'QtWebEngineProcess'))
        if os.path.exists(likely_qtwebengineprocess):
            os.environ['QTWEBENGINEPROCESS_PATH'] = likely_qtwebengineprocess

        self.inputPane = EditFile(self.project.filename('inp', run=-1), latency)
        self.setWindowTitle(filename)

        self.outputPanes = {
            suffix: ViewProjectOutput(self.project, suffix) for suffix in ['out', 'log']}

        self.webEngineProfiles = []

        menubar = MenuBar(self)
        self.setMenuBar(menubar)

        menubar.addAction('New', 'File', slot=self.newAction, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addAction('Close', 'File', self.close, 'Ctrl+W')
        menubar.addAction('Open', 'File', self.chooserOpen, 'Ctrl+O', 'Open another project')
        menubar.addSeparator('File')
        menubar.addAction('Quit', 'File', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')

        menubar.addAction('Build', 'Edit', self.editInputStructure, 'Ctrl+D', 'Edit molecular geometry')
        menubar.addAction('Cut', 'Edit', self.inputPane.cut, 'Ctrl+X', 'Cut')
        menubar.addAction('Copy', 'Edit', self.inputPane.copy, 'Ctrl+C', 'Copy')
        menubar.addAction('Paste', 'Edit', self.inputPane.paste, 'Ctrl+V', 'Paste')
        menubar.addAction('Undo', 'Edit', self.inputPane.undo, 'Ctrl+Z', 'Undo')
        menubar.addAction('Redo', 'Edit', self.inputPane.redo, 'Shift+Ctrl+Z', 'Redo')
        menubar.addAction('Select All', 'Edit', self.inputPane.selectAll, 'Ctrl+A', 'Redo')
        menubar.addSeparator('Edit')
        menubar.addAction('Zoom In', 'Edit', self.inputPane.zoomIn, 'Shift+Ctrl+=', 'Increase font size')
        menubar.addAction('Zoom Out', 'Edit', self.inputPane.zoomOut, 'Ctrl+-', 'Decrease font size')
        menubar.addSeparator('Edit')
        self.guidedAction = menubar.addAction('Guided mode', 'Edit', self.guidedToggle, 'Ctrl+G', checkable=True)

        menubar.addAction('Import input', 'Project', self.importInput, 'Ctrl+Shift+I',
                          tooltip='Import a file and assign it as the input for the project')
        menubar.addAction('Import file', 'Project', self.importFile, 'Ctrl+I',
                          tooltip='Import one or more files, eg geometry definition, into the project')
        menubar.addAction('Export file', 'Project', self.exportFile, 'Ctrl+E',
                          tooltip='Export one or more files from the project')
        runAction = menubar.addAction('Run', 'Project', self.run, 'Ctrl+R', 'Run Molpro on the project input')
        killAction = menubar.addAction('Kill', 'Project', self.kill, tooltip='Kill the running job')
        menubar.addAction('Backend', 'Project', lambda: configureBackend(self), 'Ctrl+B', 'Configure backend')
        menubar.addAction('Edit backend configuration file', 'Project', self.editBackendConfiguration, 'Ctrl+Shift+B',
                          'Edit backend configuration file')
        menubar.addAction('Clean', 'Project', self.clean, tooltip='Remove old runs from the project')
        menubar.show()

        menubar.addAction('Zoom In', 'View', lambda: [p.zoomIn() for p in self.outputPanes.values()], 'Alt+Shift+=',
                          'Increase font size')
        menubar.addAction('Zoom Out', 'View', lambda: [p.zoomOut() for p in self.outputPanes.values()], 'Alt+-',
                          'Decrease font size')
        menubar.addSeparator('View')
        menubar.addAction('Input structure', 'View', self.visinp,
                          tooltip='View the molecular structure in the job input')
        menubar.addAction('Output structure', 'View', self.visout, 'Alt+D',
                          tooltip='View the molecular structure at the end of the job')
        menubar.addSeparator('View')

        # for a in menubar.actions():
        #     print(a, type(a), a.menu(), a.menu().title())
        #     for b in a.menu().actions():
        #         print(b, b.text(), b.shortcut(), b.toolTip())

        helpManager = HelpManager(menubar)
        helpManager.register('Overview', 'README')
        helpManager.register('Another', 'something else')
        helpManager.register('Backends', 'doc/backends.md')

        self.runButton = QPushButton('Run')
        self.runButton.clicked.connect(runAction.trigger)
        self.runButton.setToolTip("Run the job")
        self.killButton = QPushButton('Kill')
        self.killButton.clicked.connect(killAction.trigger)
        self.killButton.setToolTip("Kill the running job")

        self.statusBar = StatusBar(self.project, self.runButton, self.killButton)
        self.statusBar.refresh()

        leftLayout = QVBoxLayout()
        self.inputTabs = QTabWidget()
        self.inputTabs.setTabBarAutoHide(True)
        self.inputTabs.setDocumentMode(True)
        self.inputTabs.setTabPosition(QTabWidget.South)
        self.inputTabs.currentChanged.connect(self.refreshInputTabs)
        self.refreshInputTabs()
        leftLayout.addWidget(self.inputTabs)
        self.inputTabs.setMinimumHeight(300)
        self.inputTabs.setMinimumWidth(400)
        self.statusBar.setMaximumWidth(400)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.runButton)
        buttonLayout.addWidget(self.killButton)
        self.VODselector = QComboBox()
        buttonLayout.addWidget(QLabel('Visual object display:'))
        buttonLayout.addWidget(self.VODselector)
        leftLayout.addLayout(buttonLayout)
        leftLayout.addWidget(self.statusBar)

        toplayout = QHBoxLayout()
        toplayout.addLayout(leftLayout)
        self.outputTabs = QTabWidget()
        self.outputTabs.setTabBarAutoHide(True)
        self.outputTabs.setDocumentMode(True)
        self.outputTabs.setTabPosition(QTabWidget.South)
        self.refreshOutputTabs()
        self.timerOutputTabs = QTimer()
        self.timerOutputTabs.timeout.connect(self.refreshOutputTabs)
        self.timerOutputTabs.start(2000)
        toplayout.addWidget(self.outputTabs)

        self.layout = QVBoxLayout()
        self.layout.addLayout(toplayout)
        self.VOD = None

        self.rebuildVODselector()
        self.outputPanes['out'].textChanged.connect(self.rebuildVODselector)
        self.VODselector.currentTextChanged.connect(self.VODselectorAction)
        self.minimumWindowSize = self.window().size()

        # self.layout.setSizeConstraint(QLayout.SetFixedSize)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def editBackendConfiguration(self):
        self.backendConfigurationEditor = MainEditFile(pathlib.Path.home() / '.sjef/molpro/backends.xml')
        self.backendConfigurationEditor.show()

    def editInputStructure(self):
        f = self.geometryfiles()
        if f:
            filename = self.project.filename('', f[-1][1], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            self.embedded_builder(filename)

    def refreshOutputTabs(self):
        if len(self.outputTabs) != len(
                [suffix for suffix, pane in self.outputPanes.items() if os.path.exists(self.project.filename(suffix))]):
            self.outputTabs.clear()
            for suffix, pane in self.outputPanes.items():
                if os.path.exists(self.project.filename(suffix)):
                    self.outputTabs.addTab(pane, suffix)

    def guidedToggle(self):
        self.refreshInputTabs(index=1 if self.guidedAction.isChecked() else 0)

    def refreshInputTabs(self, index=0):
        input = self.inputPane.toPlainText()
        if not input: input = ''
        self.inputSpecification = molpro_input.parse(input)
        guided = molpro_input.equivalent(input,self.inputSpecification)
        # print('input:', input)
        # print('specification:', self.inputSpecification)
        # print('guided:', guided)
        if not guided and index == 1:
            box = QMessageBox()
            box.setText('Guided mode cannot be used because the input is too complex')
            box.exec()
            self.guidedAction.setChecked(False)
        if len(self.inputTabs) < 1:
            self.inputTabs.addTab(self.inputPane, 'freehand')
        if not guided and len(self.inputTabs) != 1:
            self.inputTabs.removeTab(1)
        if guided and len(self.inputTabs) != 2:
            self.guidedPane = QLabel()
            self.inputTabs.addTab(self.guidedPane, 'guided')
        self.inputTabs.setCurrentIndex(index if index >= 0 and index < len(self.inputTabs) else len(self.inputTabs) - 1)
        if guided and self.inputTabs.currentIndex() == 1:
            self.guidedPane.setText(re.sub('}$','\n}',re.sub('^{','{\n  ',str(self.inputSpecification))).replace(', ',',\n  '))

    def VODselectorAction(self):
        text = self.VODselector.currentText().strip()
        if text == '':
            return
        elif text == 'None':
            if self.VOD:
                self.VOD.hide()
                self.window().resize(
                    self.minimumWindowSize)  # TODO find a way of shrinking back the main window # self.inputPane.adjustSize() # self.outputPane.adjustSize() # self.adjustSize()
        elif text[:5] == 'Edit ':
            filename = self.project.filename('', text[5:], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            self.embedded_builder(filename)
        elif text == 'Input':
            self.visinp()
        elif text == 'Output':
            self.visout(False, 'xml')
        else:
            self.visout(False, '', text)

    def rebuildVODselector(self):
        self.VODselector.clear()
        self.VODselector.addItem('None')
        for t, f in self.geometryfiles():
            self.VODselector.addItem('Edit ' + f)
        self.VODselector.addItem('Input')
        if self.project.status == 'completed' or (
                os.path.isfile(self.project.filename('xml')) and open(self.project.filename('xml'),
                                                                      'r').read().rstrip()[
                                                                 -9:] == '</molpro>'):
            self.VODselector.addItem('Output')
            for t, f in self.putfiles():
                self.VODselector.addItem(f)

    def putfiles(self):
        result = []
        lines = self.inputPane.toPlainText().replace(';', '\n').split('\n')
        for line in lines:
            fields = line.replace(' ', ',').split(',')
            if len(fields) > 2 and fields[0].lower() == 'put':
                result.append((fields[1], fields[2]))
        return result

    def geometryfiles(self):
        import re
        result = []
        lines = self.inputPane.toPlainText().replace(';', '\n').split('\n')
        for line in lines:
            fields = line.replace(' ', ',').split(',')
            regex = r'geometry=([-@#&a-z0-9_]+)\.(xyz)'
            if len(fields) == 1 and re.match(regex, fields[0], re.IGNORECASE):
                result.append((re.sub(regex, r'\2', fields[0]), re.sub(regex, r'\1.\2', fields[0])))
        return result

    def run(self):
        self.project.run()

    def kill(self):
        self.project.kill()

    def clean(self):
        self.project.clean()

    def visout(self, param, typ='xml', name=None):
        if name:
            self.embedded_VOD(self.project.filename(typ, name), command='mo HOMO')
        else:
            self.embedded_VOD(self.project.filename(typ), command='mo HOMO')

    def embedded_VOD(self, file, command='', **kwargs):
        firstmodel = 1
        try:
            vibs = factoryVibrationSet(file, **kwargs)
            firstmodel = firstvib = vibs.coordinateSet
        except (IndexError, KeyError):
            vibs = None
        try:
            orbs = factoryOrbitalSet(file, **kwargs)
            firstmodel = firstorb = orbs.coordinateSet
        except (IndexError, KeyError):
            orbs = None
        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src=" """ + self.JSmolMinJS + """"> </script>
</head>
<body>
<table>
<tr valign="top"><td>
<script>
var Info = {
  color: "#FFFFFF",
  height: 400,
  width: 400,
  script: "load """ + file + """; set antialiasDisplay ON; set showFrank OFF; model """ + str(
            firstmodel) + """; """ + command + """; mo nomesh fill translucent 0.3; mo resolution 7",
  use: "HTML5",
  j2sPath: "j2s",
  serverURL: "php/jsmol.php",
};

Jmol.getApplet("myJmol", Info);
</script>
</td>
<td>
<script>
Jmol.jmolLink(myJmol,'menu','Jmol menu')
</script>
<br><table><tr>
"""
        if vibs and vibs.frequencies:
            html += """
<script>
Jmol.jmolHtml('<td>Vibrations: ')
Jmol.jmolHtml(' ')
Jmol.jmolCheckbox(myJmol,"vibration on", "vibration off", "animate", 1)
Jmol.jmolHtml(' ')
Jmol.script(myJmol, 'color vectors yellow')
Jmol.jmolCheckbox(myJmol,"vectors on", "vectors off", "vectors")
Jmol.jmolHtml(' ')
Jmol.jmolBr()
Jmol.jmolMenu(myJmol,[
"""
            for frequency in vibs.frequencies:
                if abs(frequency) > 1.0:
                    html += '["frame ' + str(firstvib) + '; vibration on", "' + str(frequency) + '"],'
                firstvib += 1
            html += """
],10);
Jmol.jmolBr()
</script>
</td>
             """

        if orbs and orbs.energies:
            html += """
<script>
Jmol.script(myJmol, 'frame  """
            html += str(firstorb)
            html += """')
Jmol.jmolHtml('<td>Orbitals: ')
Jmol.jmolBr()
Jmol.jmolMenu(myJmol,[
"""
            energyReverse = list(orbs.energies)
            energyReverse.reverse()
            i = len(energyReverse)
            for energy in energyReverse:
                html += '["model ' + str(firstorb) + '; vibration off; mo ' + str(i) + '", "' + str(energy) + '"],'
                i -= 1
            html += """
],10);
Jmol.jmolBr()
</script>
</td>
             """

        html += """
        </tr>
<script>
Jmol.jmolCommandInput(myJmol,'Type Jmol commands here',40,1,'title')
</script>
</td>
</tr>
</body>
</html>"""
        self.addVOD(html, **kwargs)

    def embedded_builder(self, file, **kwargs):

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src=" """ + self.JSmolMinJS + """"> </script>
</head>
<body>
<table>
<tr valign="top"><td>
<script>
var Info = {
  color: "#FFFFFF",
  height: 400,
  width: 400,
  script: "set antialiasDisplay ON;"""
        html += ' load ' + file + ';'
        html += """ set showFrank OFF; set modelKitMode on",
  use: "HTML5",
  j2sPath: "j2s",
  serverURL: "php/jsmol.php",
};

Jmol.getApplet("myJmol", Info);
</script>
</td>
<td>
Click in the top left corner of the display pane for options.<br/>
<script>
Jmol.jmolButton(myJmol, 'write """
        filetype = os.path.splitext(file)[1][1:]
        html += filetype + ' "' + file
        html += """\"','Save structure')
Jmol.jmolLink(myJmol,'menu','Jmol menu')
Jmol.jmolBr()
Jmol.jmolCommandInput(myJmol,'Type Jmol commands here',40,1,'title')
</script>
</td>
</tr>
</body>
</html>"""

        self.addVOD(html, **kwargs)

    def addVOD(self, html, width=400, height=420, verbosity=0):
        if verbosity:
            print(html)
            open('test.html', 'w').write(html)
        webview = QWebEngineView()
        profile = QWebEngineProfile()
        self.webEngineProfiles.append(
            profile)  # FIXME This to avoid premature garbage collection. A resource leak. Need to find a way to delete the previous QWebEnginePage instead
        profile.downloadRequested.connect(self._download_requested)
        page = QWebEnginePage(profile, webview)
        page.setHtml(html, QUrl.fromLocalFile(str(pathlib.Path(__file__).resolve())))
        webview.setPage(page)

        webview.setMinimumSize(width, height)
        if not self.VOD:
            self.layout.addWidget(webview)
        else:
            self.layout.replaceWidget(self.VOD, webview)
            self.VOD.hide()
        self.VOD = webview
        self.VOD.show()

    def _download_requested(self, item):
        import re
        if item.downloadFileName():
            item.setDownloadFileName(re.sub(r' \(\d+\)\.', r'.', item.downloadFileName()))
            item.setDownloadDirectory(self.project.filename(run=-1))
            item.accept()

    def visinp(self, param=False):
        import tempfile
        geometryDirectory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometryDirectory.mkdir(exist_ok=True)
        xyzFile = str(geometryDirectory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        if not os.path.isfile(xyzFile) or os.path.getmtime(xyzFile) < os.path.getmtime(
                self.project.filename('inp', run=-1)) or any(
            [os.path.getmtime(xyzFile) < os.path.getmtime(self.project.filename('', gfile[1], run=-1)) for gfile in
             self.geometryfiles()]):
            with tempfile.TemporaryDirectory() as tmpdirname:
                self.project.copy(pathlib.Path(self.project.filename(run=-1)).name, location=tmpdirname)
                projectPath = pathlib.Path(tmpdirname) / pathlib.Path(self.project.filename(run=-1)).name
                project = Project(str(projectPath))
                project.clean(0)
                open(project.filename('inp', run=-1), 'a').write('\nhf\n---')
                with open(pathlib.Path(project.filename(run=-1)) / 'molpro.rc', 'a') as f:
                    f.write(' --geometry')
                project.run(wait=True, force=True, backend='local')
                if not project.xpath_search('//*/cml:atomArray'):
                    print(project.out)
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setWindowTitle("Error")
                    msg.setText('Error in calculating input geometry')
                    msg.exec_()
                    return
                geometry = project.geometry()
                with open(xyzFile, 'w') as f:
                    f.write(str(len(geometry)) + '\n\n')
                    for atom in geometry:
                        f.write(atom['elementType'])
                        for c in atom['xyz']: f.write(' ' + str(c * .529177210903))
                        f.write('\n')
        self.embedded_VOD(xyzFile, command='')

    def closeEvent(self, a0):
        self.closeSignal.emit(self)

    def newAction(self):
        self.newSignal.emit(self)

    def chooserOpen(self):
        self.chooserSignal.emit(self)

    def clean(self):
        self.project.clean(1)

    def importFile(self):
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Import file(s) into project', )
        for filename in filenames:
            if os.path.isfile(filename):
                self.project.import_file(filename)

    def importInput(self):
        filename, junk = QFileDialog.getOpenFileName(self, 'Copy file to project input', )
        if os.path.isfile(filename):
            self.project.import_input(filename)

    def exportFile(self):
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Export file(s) from the project', self.project.filename())
        for filename in filenames:
            if os.path.isfile(filename):
                b = os.path.basename(filename)
                dest = QFileDialog.getExistingDirectory(self, 'Destination for ' + b)
                shutil.copy(filename, dest)
