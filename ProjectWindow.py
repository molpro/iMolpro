import os
import pathlib
import shutil

from PyQt5.QtCore import QTimer, pyqtSignal, QUrl
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QShortcut, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QMessageBox, QMenuBar, QTabWidget, QAction, QFileDialog
from pymolpro import Project

from utilities import EditFile, ViewFile, factoryVibrationSet, factoryOrbitalSet


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


class OutputPane:
    def __init__(self, project, suffix='out', width=800, latency=100, fileNameLatency=2000):
        self.project = project
        self.suffix = suffix
        self.filename = self.project.filename(suffix)
        self.outputPane = ViewFile(self.filename, latency=latency)
        self.outputPane.setMinimumWidth(width)
        self.refreshOutputFileTimer = QTimer()
        self.refreshOutputFileTimer.timeout.connect(self.refreshOutputFile)
        self.refreshOutputFileTimer.start(fileNameLatency)  # find a better way

    def refreshOutputFile(self):
        latestFilename = self.project.filename(self.suffix)
        if latestFilename != self.filename:
            self.outputPane.reset(latestFilename)
            self.filename = latestFilename


class ProjectWindow(QMainWindow):
    closeSignal = pyqtSignal(QWidget)
    newSignal = pyqtSignal(QWidget)
    chooserSignal = pyqtSignal(QWidget)

    def addAction(self, name: str, slot=None, menu: str = None, shortcut: str = None, tooltip: str = None):
        if not hasattr(self, 'actions_'): self.actions_ = {}
        key = menu + '/' + name if menu else name
        assert key not in self.actions_.keys()
        self.actions_[key] = QAction(name)
        if menu: self.menus[menu].addAction(self.actions_[key])
        if slot: self.actions_[key].triggered.connect(slot)
        if shortcut: self.actions_[key].setShortcut(shortcut)
        if tooltip: self.actions_[key].setToolTip(tooltip)
        return self.actions_[key]

    def __init__(self, filename=None, latency=1000):
        super().__init__()

        assert filename is not None
        self.project = Project(filename)

        self.inputPane = EditFile(self.project.filename('inp', run=-1), latency)
        self.setWindowTitle(filename)

        self.outputPanes = {
            suffix: OutputPane(self.project, suffix) for suffix in ['out', 'log']}

        self.webEngineProfiles = []

        menubar = QMenuBar()
        self.setMenuBar(menubar)
        self.menus = {m: menubar.addMenu(m) for m in ['File', 'Edit', 'Project', 'View', 'Help']}
        for m in self.menus.values(): m.setToolTipsVisible(True)

        self.addAction('New', slot=self.newAction, menu='File', shortcut='Ctrl+N', tooltip='Create a new project')
        self.addAction('Close', self.close, 'File', 'Ctrl+W')
        self.addAction('Open', self.chooserOpen, 'File', 'Ctrl+O', 'Open another project')

        self.addAction('Build', self.editInputStructure, 'Edit', 'Ctrl+D', 'Edit molecular geometry')
        self.addAction('Cut', self.inputPane.cut, 'Edit', 'Ctrl+X', 'Cut')
        self.addAction('Copy', self.inputPane.copy, 'Edit', 'Ctrl+C', 'Copy')
        self.addAction('Paste', self.inputPane.paste, 'Edit', 'Ctrl+X', 'Paste')
        self.addAction('Undo', self.inputPane.undo, 'Edit', 'Ctrl+Z', 'Undo')
        self.addAction('Redo', self.inputPane.redo, 'Edit', 'Shift+Ctrl+Z', 'Redo')
        self.addAction('Select All', self.inputPane.selectAll, 'Edit', 'Ctrl+A', 'Redo')
        self.addAction('Zoom In', self.inputPane.zoomIn, 'Edit', 'Shift+Ctrl+=', 'Increase font size')
        self.addAction('Zoom Out', self.inputPane.zoomOut, 'Edit', 'Ctrl+-', 'Decrease font size')

        self.addAction('Import file', self.importFile, 'Project',
                       tooltip='Import one or more files, eg geometry definition, into the project')
        self.addAction('Export file', self.exportFile, 'Project', tooltip='Export one or more files from the project')
        runAction = self.addAction('Run', self.run, 'Project', 'Ctrl+R', 'Run Molpro on the project input')
        killAction = self.addAction('Kill', self.kill, 'Project', tooltip='Kill the running job')
        self.addAction('Backend', self.backend, 'Project', 'Ctrl+B', 'Configure backend')
        self.addAction('Clean', self.clean, 'Project', tooltip='Remove old runs from the project')
        menubar.show()

        # self.addAction('Zoom In',self.outputPanes[0].zoomIn, 'View','Alt+Shift+=','Increase font size')
        # self.addAction('Zoom Out',self.outputPanes[0].zoomOut, 'View','Alt+-','Decrease font size')
        self.addAction('Input structure', self.visinp, 'View', tooltip='View the molecular structure in the job input')
        self.addAction('Output structure', self.visout, 'View',
                       tooltip='View the molecular structure at the end of the job')

        self.runButton = QPushButton('Run')
        self.runButton.clicked.connect(runAction.trigger)
        self.runButton.setToolTip("Run the job")
        self.killButton = QPushButton('Kill')
        self.killButton.clicked.connect(killAction.trigger)
        self.killButton.setToolTip("Kill the running job")

        self.statusBar = StatusBar(self.project, self.runButton, self.killButton)
        self.statusBar.refresh()

        leftLayout = QVBoxLayout()
        leftLayout.addWidget(self.inputPane)
        self.inputPane.setMinimumHeight(300)
        self.inputPane.setMinimumWidth(400)
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
        self.outputPanes['out'].outputPane.textChanged.connect(self.rebuildVODselector)
        self.VODselector.currentTextChanged.connect(self.VODselectorAction)
        self.minimumWindowSize = self.window().size()

        # self.layout.setSizeConstraint(QLayout.SetFixedSize)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

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
                    self.outputTabs.addTab(pane.outputPane, suffix)

    def VODselectorAction(self):
        text = self.VODselector.currentText().strip()
        if text == '':
            return
        elif text == 'None':
            if self.VOD:
                self.VOD.hide()
                self.window().resize(self.minimumWindowSize)  # TODO find a way of shrinking back the main window
                # self.inputPane.adjustSize()
                # self.outputPane.adjustSize()
                # self.adjustSize()
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
            regex = r'geometry=([-@#&A-Za-z0-9_]+)\.(xyz)'
            if len(fields) == 1 and re.match(regex, fields[0], re.IGNORECASE):
                result.append((re.sub(regex, r'\2', fields[0]), re.sub(regex, r'\1.\2', fields[0])))
        return result

    def run(self):
        self.project.run()

    def kill(self):
        self.project.kill()

    def clean(self):
        self.project.clean()

    def backend(self):
        pass  # TODO implement

    def visout(self, param, typ='xml', name=None):
        if name:
            self.embedded_VOD(self.project.filename(typ, name), command='mo HOMO')
        else:
            self.embedded_VOD(self.project.filename(typ), command='mo HOMO')

    def embedded_VOD(self, file, command='', **kwargs):
        webview = QWebEngineView()
        firstmodel = 1
        try:
            vibs = factoryVibrationSet(file, **kwargs)
            firstmodel = firstvib = vibs.coordinateSet
        except:
            vibs = None
        try:
            orbs = factoryOrbitalSet(file, **kwargs)
            firstmodel = firstorb = orbs.coordinateSet
        except:
            orbs = None
        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src="./JSmol.min.js"> </script>
</head>
<body>
<table>
<tr valign="top"><td>
<script>
var Info = {
  color: "#FFFFFF",
  height: 400,
  width: 400,
  script: "load """ + file + """; set antialiasDisplay ON; set showFrank OFF; model """ + str(firstmodel) + """; """ + command + """; mo nomesh fill translucent 0.3; mo resolution 7",
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
            energy_reverse = list(orbs.energies)
            energy_reverse.reverse()
            i = len(energy_reverse)
            for energy in energy_reverse:
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
<script type="text/javascript" src="JSmol.min.js"> </script>
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

    def visinp(self, param):
        import tempfile
        geometry_directory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometry_directory.mkdir(exist_ok=True)
        xyzFile = str(geometry_directory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        if os.path.isfile(xyzFile):
            for gfile in self.geometryfiles():
                fn = self.project.filename('', gfile[1], run=-1)
        if not os.path.isfile(xyzFile) or os.path.getmtime(xyzFile) < os.path.getmtime(
                self.project.filename('inp', run=-1)) or any(
            [os.path.getmtime(xyzFile) < os.path.getmtime(self.project.filename('', gfile[1], run=-1)) for gfile in
             self.geometryfiles()]):
            with tempfile.TemporaryDirectory() as tmpdirname:
                self.project.copy(pathlib.Path(self.project.filename(run=-1)).name, location=tmpdirname)
                project_path = pathlib.Path(tmpdirname) / pathlib.Path(self.project.filename(run=-1)).name
                project = Project(str(project_path))
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
                b = os.path.basename(filename)
                dest = self.project.filename('', b)
                shutil.copyfile(filename, dest)

    def exportFile(self):
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Export file(s) from the project', self.project.filename())
        for filename in filenames:
            if os.path.isfile(filename):
                b = os.path.basename(filename)
                dest = QFileDialog.getExistingDirectory(self, 'Destination for ' + b)
                shutil.copy(filename, dest)
