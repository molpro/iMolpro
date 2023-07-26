from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPlainTextEdit, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QMessageBox
from PyQt5.QtGui import QFont, QFontDatabase
from pymolpro import Project
import sys
import os
import pathlib


class EditFile(QPlainTextEdit):
    def __init__(self, filename: str, latency=1000):
        super().__init__()
        self.filename = str(filename)
        if os.path.isfile(self.filename):
            with open(self.filename, 'r') as f:
                self.savedText = f.read()
        else:
            self.savedText = ''
        self.setPlainText(self.savedText)
        f = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        f.setPointSize(12)
        self.setFont(f)

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


def launchExternalViewer(file):
    import subprocess
    try:
        viewer = 'jmol'
        subprocess.Popen([viewer, file])
    except:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Error")
        msg.setText('Cannot launch ' + viewer)
        msg.setInformativeText('Perhaps needs to be installed somewhere in $PATH?')
        msg.exec_()


class ProjectWindow(QMainWindow):
    def __init__(self, filename=None, latency=1000):
        super().__init__()

        assert filename is not None  # TODO eventually pop dialog for this

        self.project = Project(filename)  # TODO some error checking needed
        self.inputPane = EditFile(self.project.filename('inp', run=-1), latency)
        self.setWindowTitle(filename)
        self.runButton = QPushButton('Run')
        self.runButton.clicked.connect(self.run)
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
        buttonLayout.addWidget(self.visinpButton)
        buttonLayout.addWidget(self.runButton)
        buttonLayout.addWidget(self.visoutButton)
        putButtons = []

        class VisoutButton(QPushButton):
            def __init__(self, name, f):
                super().__init__(name)
                self.action = f
                self.clicked.connect(lambda: self.action('', self.text()))

        for t, f in self.putfiles():
            putButtons.append(VisoutButton(f, self.visout))
            buttonLayout.addWidget(putButtons[-1])
        leftLayout.addLayout(buttonLayout)
        leftLayout.addWidget(self.statusBar)

        self.outputPane = ViewFile(self.project.filename('out'), latency=100)
        self.outputPane.setMinimumWidth(800)
        self.refreshOutputFileTimer = QTimer()
        self.refreshOutputFileTimer.timeout.connect(self.refreshOutputFile)
        self.refreshOutputFileTimer.start(2000)  # find a better way

        layout = QHBoxLayout()
        layout.addLayout(leftLayout)
        layout.addWidget(self.outputPane)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

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
        # filename = self.project.filename('molden')
        # with open(filename, 'w') as f:
        #     f.write(to_molden(self.project))
        # launchExternalViewer(filename)
        if name:
            launchExternalViewer(self.project.filename(typ, name))
        else:
            launchExternalViewer(self.project.filename(typ))

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
        launchExternalViewer(xyzFile)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    windows = []
    for arg in sys.argv[1:]:
        windows.append(ProjectWindow(arg))
        windows[-1].show()

    app.exec()
