import os
import pathlib
import sys

from PyQt5.QtCore import QTimer, pyqtSignal, QUrl
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QShortcut, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QMessageBox
from pymolpro import Project

from utilities import EditFile, ViewFile


class StatusBar(QLabel):
    def __init__(self, project, latency=1000):
        super().__init__()
        self.project = project
        self.refreshTimer = QTimer()
        self.refreshTimer.timeout.connect(self.refresh)
        self.refreshTimer.start(latency)

    def refresh(self):
        self.setText('Status: ' + ('run ' + pathlib.Path(
            self.project.filename()).stem + ' ' if self.project.filename() != self.project.filename(
            run=-1) else '') + self.project.status)


class ProjectWindow(QMainWindow):
    closeSignal = pyqtSignal(QWidget)

    def __init__(self, filename=None, latency=1000):
        super().__init__()

        assert filename is not None  # TODO eventually pop dialog for this

        menubar = self.menuBar()
        menubar.addMenu('&File')
        self.closeShortcut = QShortcut(QKeySequence('Ctrl+W'), self)
        self.closeShortcut.activated.connect(self.close)

        self.project = Project(filename)  # TODO some error checking needed
        self.inputPane = EditFile(self.project.filename('inp', run=-1), latency)
        self.setWindowTitle(filename)
        self.runButton = QPushButton('&Run')
        self.runButton.clicked.connect(self.run)
        self.runShortcut = QShortcut(QKeySequence('Ctrl+R'), self)
        self.runShortcut.activated.connect(self.run)
        self.visoutButton = QPushButton('Visualise output')
        self.visoutButton.clicked.connect(lambda: self.visout('xml'))
        self.visinpButton = QPushButton('Visualise input')
        self.visinpButton.clicked.connect(self.visinp)

        self.statusBar = StatusBar(self.project)

        leftLayout = QVBoxLayout()
        leftLayout.addWidget(self.inputPane)
        self.inputPane.setMinimumHeight(300)
        self.inputPane.setMinimumWidth(400)
        self.statusBar.setMaximumWidth(400)
        buttonLayout = QHBoxLayout()
        # buttonLayout.addWidget(self.visinpButton)
        buttonLayout.addWidget(self.runButton)
        # buttonLayout.addWidget(self.visoutButton)
        self.VODselector = QComboBox()
        # putButtons = []

        # class VisoutButton(QPushButton):
        #     def __init__(self, name, f):
        #         super().__init__(name)
        #         self.action = f
        #         self.clicked.connect(lambda: self.action('', self.text()))
        #
        # for t, f in self.putfiles():
        #     putButtons.append(VisoutButton(f, self.visout))
        #     buttonLayout.addWidget(putButtons[-1])
        buttonLayout.addWidget(QLabel('Visual object display:'))
        buttonLayout.addWidget(self.VODselector)
        leftLayout.addLayout(buttonLayout)
        leftLayout.addWidget(self.statusBar)

        self.outputPane = ViewFile(self.project.filename('out'), latency=100)
        self.outputPane.setMinimumWidth(800)
        self.refreshOutputFileTimer = QTimer()
        self.refreshOutputFileTimer.timeout.connect(self.refreshOutputFile)
        self.refreshOutputFileTimer.start(2000)  # find a better way

        toplayout = QHBoxLayout()
        toplayout.addLayout(leftLayout)
        toplayout.addWidget(self.outputPane)

        self.layout = QVBoxLayout()
        self.layout.addLayout(toplayout)
        self.VOD = None

        self.rebuildVODselector()
        self.outputPane.textChanged.connect(self.rebuildVODselector)
        self.VODselector.currentTextChanged.connect(self.VODselectorAction)
        self.minimumWindowSize = self.window().size()

        # self.layout.setSizeConstraint(QLayout.SetFixedSize)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

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
        elif text == 'Input':
            self.visinp()
        elif text == 'Output':
            self.visout('xml')
        else:
            self.visout('', text)

    def rebuildVODselector(self):
        self.VODselector.clear()
        self.VODselector.addItem('None')
        self.VODselector.addItem('Input')
        if self.project.status == 'completed' or (
                os.path.isfile(self.project.filename('xml')) and open(self.project.filename('xml'),
                                                                      'r').read().rstrip()[
                                                                 -9:] == '</molpro>'):
            self.VODselector.addItem('Output')
            for t, f in self.putfiles():
                self.VODselector.addItem(f)

    def addVOD(self, vod: QWidget):
        if not self.VOD:
            self.layout.addWidget(vod)
        else:
            self.layout.replaceWidget(self.VOD, vod)
            self.VOD.hide()
        self.VOD = vod
        self.VOD.show()

    def putfiles(self):
        result = []
        lines = self.inputPane.toPlainText().replace(';', '\n').split('\n')
        for line in lines:
            fields = line.replace(' ', ',').split(',')
            if len(fields) > 2 and fields[0].lower() == 'put':
                result.append((fields[1], fields[2]))
        return result

    def refreshOutputFile(self):
        self.outputPane.reset(self.project.filename('out'))

    def run(self):
        self.project.run()

    def visout(self, typ='xml', name=None):
        if name:
            self.embedded_VOD(self.project.filename(typ, name), command='mo HOMO')
        else:
            self.embedded_VOD(self.project.filename(typ), command='mo HOMO')

    def embedded_VOD(self, file, command='', **kwargs):
        webview = QWebEngineView()

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src="JSmol.min.js"> </script>
</head>
<body>
<script>
var Info = {
  color: "#FFFFFF",
  height: 400,
  width: 400,
  script: "load """ + file + """; """ + command + """; mo nomesh fill translucent 0.3; mo resolution 7; set antialiasDisplay ON",
  use: "HTML5",
  j2sPath: "j2s",
  serverURL: "php/jsmol.php",
};

Jmol.getApplet("myJmol", Info);
</script>
</body>
</html>"""
        cwd = str(pathlib.Path(__file__).resolve())
        webview.setHtml(html, QUrl.fromLocalFile(cwd))

        webview.setMinimumSize(400, 420)
        self.addVOD(webview)

    def visinp(self):
        import tempfile
        geometry_directory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometry_directory.mkdir(exist_ok=True)
        xyzFile = str(geometry_directory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        if not os.path.isfile(xyzFile) or os.path.getmtime(xyzFile) < os.path.getmtime(
                self.project.filename('inp', run=-1)):
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
