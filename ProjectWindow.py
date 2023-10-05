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
from RecentMenu import RecentMenu
from database import database_choose_structure
from help import HelpManager
from utilities import EditFile, ViewFile, factory_vibration_set, factory_orbital_set, MainEditFile
from backend import configure_backend
from settings import settings


class StatusBar(QLabel):
    def __init__(self, project: Project, run_actions: list, kill_actions: list, latency=1000):
        super().__init__()
        self.project = project
        self.run_actions = run_actions
        self.kill_actions = kill_actions
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(latency)

    def refresh(self):
        self.setText('Status: ' + ('run ' + pathlib.Path(
            self.project.filename()).stem + ' ' if self.project.filename() != self.project.filename(
            run=-1) else '') + self.project.status)
        for run_action in self.run_actions:
            run_action.setDisabled(not self.project.run_needed())
        for kill_action in self.kill_actions:
            kill_action.setDisabled(self.project.status != 'running' and self.project.status != 'waiting')


class ViewProjectOutput(ViewFile):
    def __init__(self, project, suffix='out', width=800, latency=100, filename_latency=2000):
        self.project = project
        self.suffix = suffix
        super().__init__(self.project.filename(suffix), latency=latency)
        super().setMinimumWidth(width)
        self.refresh_output_file_timer = QTimer()
        self.refresh_output_file_timer.timeout.connect(self.refresh_output_file)
        self.refresh_output_file_timer.start(filename_latency)  # find a better way

    def refresh_output_file(self):
        latest_filename = self.project.filename(self.suffix)
        if latest_filename != self.filename:
            self.reset(latest_filename)


class ProjectWindow(QMainWindow):
    close_signal = pyqtSignal(QWidget)
    new_signal = pyqtSignal(QWidget)
    chooser_signal = pyqtSignal(QWidget)
    vod = None

    def __init__(self, filename, window_manager, latency=1000):
        super().__init__()
        self.window_manager = window_manager

        assert filename is not None
        self.project = Project(filename)
        settings['project_directory'] = os.path.dirname(self.project.filename(run=-1))

        if 'PATH' in os.environ and 'SHELL' in os.environ:
            os.environ['PATH'] = os.popen(os.environ['SHELL'] + " -l -c 'echo $PATH'").read() + ':' + os.environ[
                'PATH']  # make PATH just as if running from shell
        self.jsmol_min_js = str(pathlib.Path(__file__).parent / "JSmol.min.js")
        if hasattr(sys, '_MEIPASS'):
            os.environ['QTWEBENGINEPROCESS_PATH'] = os.path.normpath(os.path.join(
                sys._MEIPASS, 'PyQt5', 'Qt', 'libexec', 'QtWebEngineProcess'
            ))
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox'
        likely_qtwebengineprocess = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PyQt5', 'Qt5', 'libexec', 'QtWebEngineProcess'))
        if os.path.exists(likely_qtwebengineprocess):
            os.environ['QTWEBENGINEPROCESS_PATH'] = likely_qtwebengineprocess

        self.input_pane = EditFile(self.project.filename('inp', run=-1), latency)
        if self.input_pane.toPlainText().strip('\n ') == '':
            self.input_pane.setPlainText(
                'geometry={0}.xyz\nbasis=cc-pVTZ-PP\nrhf'.format(os.path.basename(self.project.name).replace(' ', '-')))
        self.setWindowTitle(filename)

        self.output_panes = {
            suffix: ViewProjectOutput(self.project, suffix) for suffix in ['out', 'log']}

        self.webengine_profiles = []

        menubar = MenuBar(self)
        self.setMenuBar(menubar)

        menubar.addAction('New', 'File', slot=self.newAction, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addAction('Close', 'File', self.close, 'Ctrl+W')
        menubar.addAction('Open', 'File', self.chooserOpen, 'Ctrl+O', 'Open another project')
        menubar.addSeparator('File')
        self.recent_menu = RecentMenu(self.window_manager)
        menubar.addSubmenu(self.recent_menu, 'File')
        menubar.addSeparator('File')
        menubar.addAction('Quit', 'File', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')

        menubar.addAction('Structure', 'Edit', self.edit_input_structure, 'Ctrl+D', 'Edit molecular geometry')
        menubar.addAction('Cut', 'Edit', self.input_pane.cut, 'Ctrl+X', 'Cut')
        menubar.addAction('Copy', 'Edit', self.input_pane.copy, 'Ctrl+C', 'Copy')
        menubar.addAction('Paste', 'Edit', self.input_pane.paste, 'Ctrl+V', 'Paste')
        menubar.addAction('Undo', 'Edit', self.input_pane.undo, 'Ctrl+Z', 'Undo')
        menubar.addAction('Redo', 'Edit', self.input_pane.redo, 'Shift+Ctrl+Z', 'Redo')
        menubar.addAction('Select All', 'Edit', self.input_pane.selectAll, 'Ctrl+A', 'Redo')
        menubar.addSeparator('Edit')
        menubar.addAction('Zoom In', 'Edit', self.input_pane.zoomIn, 'Shift+Ctrl+=', 'Increase font size')
        menubar.addAction('Zoom Out', 'Edit', self.input_pane.zoomOut, 'Ctrl+-', 'Decrease font size')
        menubar.addSeparator('Edit')
        self.guided_action = menubar.addAction('Guided mode', 'Edit', self.guided_toggle, 'Ctrl+G', checkable=True)

        menubar.addAction('Import input', 'Project', self.import_input, 'Ctrl+Shift+I',
                          tooltip='Import a file and assign it as the input for the project')
        menubar.addAction('Import structure', 'Project', self.import_structure, 'Ctrl+Alt+I',
                          tooltip='Import an xyz file and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Search external databases for structure', 'Project', self.databaseImportStructure,
                          'Ctrl+Shift+Alt+I',
                          tooltip='Search PubChem and ChemSpider for a molecule and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Import file', 'Project', self.import_file, 'Ctrl+I',
                          tooltip='Import one or more files, eg geometry definition, into the project')
        menubar.addAction('Export file', 'Project', self.export_file, 'Ctrl+E',
                          tooltip='Export one or more files from the project')
        menubar.addAction('Clean', 'Project', self.clean, tooltip='Remove old runs from the project')
        self.run_action = menubar.addAction('Run', 'Job', self.run, 'Ctrl+R', 'Run Molpro on the project input')
        self.kill_action = menubar.addAction('Kill', 'Job', self.kill, tooltip='Kill the running job')
        menubar.addSeparator('Project')
        menubar.addAction('Browse project folder', 'Project', self.browse_project,
                          tooltip='Look at the contents of the project folder.  With care, files can be edited or renamed, but note that this may break the integrity of the project.')

        menubar.addAction('Backend', 'Job', lambda: configure_backend(self), 'Ctrl+B', 'Configure backend')
        menubar.addAction('Edit backend configuration file', 'Job', self.edit_backend_configuration, 'Ctrl+Shift+B',
                          'Edit backend configuration file')
        menubar.show()

        menubar.addAction('Zoom In', 'View', lambda: [p.zoomIn() for p in self.output_panes.values()], 'Alt+Shift+=',
                          'Increase font size')
        menubar.addAction('Zoom Out', 'View', lambda: [p.zoomOut() for p in self.output_panes.values()], 'Alt+-',
                          'Decrease font size')
        menubar.addSeparator('View')
        menubar.addAction('Input structure', 'View', self.visualise_input,
                          tooltip='View the molecular structure in the job input')
        menubar.addAction('Output structure', 'View', self.visualise_output, 'Alt+D',
                          tooltip='View the molecular structure at the end of the job')
        menubar.addSeparator('View')
        menubar.addAction('Next output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() + 1) % len(self.output_tabs)), 'Alt+]')
        menubar.addAction('Previous output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() + 1) % len(self.output_tabs)), 'Alt+[')

        help_manager = HelpManager(menubar)
        help_manager.register('Overview', 'README')
        help_manager.register('Another', 'something else')
        help_manager.register('Backends', 'doc/backends.md')

        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_action.trigger)
        self.run_button.setToolTip("Run the job")

        self.statusBar = StatusBar(self.project, [self.run_action, self.run_button], [self.kill_action])
        self.statusBar.refresh()

        left_layout = QVBoxLayout()
        self.input_tabs = QTabWidget()
        self.input_tabs.setTabBarAutoHide(True)
        self.input_tabs.setDocumentMode(True)
        self.input_tabs.setTabPosition(QTabWidget.South)
        self.input_tabs.currentChanged.connect(self.refresh_input_tabs)
        self.refresh_input_tabs()
        left_layout.addWidget(self.input_tabs)
        self.input_tabs.setMinimumHeight(300)
        self.input_tabs.setMinimumWidth(400)
        self.statusBar.setMaximumWidth(400)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.run_button)
        # button_layout.addWidget(self.killButton)
        self.vod_selector = QComboBox()
        button_layout.addWidget(QLabel('Structure display:'))
        button_layout.addWidget(self.vod_selector)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(self.statusBar)

        top_layout = QHBoxLayout()
        top_layout.addLayout(left_layout)
        self.output_tabs = QTabWidget(self)
        self.output_tabs.setTabBarAutoHide(True)
        self.output_tabs.setDocumentMode(True)
        self.output_tabs.setTabPosition(QTabWidget.South)
        self.refresh_output_tabs()
        self.timer_output_tabs = QTimer()
        self.timer_output_tabs.timeout.connect(self.refresh_output_tabs)
        self.timer_output_tabs.start(2000)
        top_layout.addWidget(self.output_tabs)

        self.layout = QVBoxLayout()
        self.layout.addLayout(top_layout)
        self.vod = None

        self.rebuild_vod_selector()
        self.output_panes['out'].textChanged.connect(self.rebuild_vod_selector)
        self.vod_selector.currentTextChanged.connect(self.vod_selector_action)
        self.minimum_window_size = self.window().size()

        # self.layout.setSizeConstraint(QLayout.SetFixedSize)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def edit_backend_configuration(self):
        self.backend_configuration_editor = MainEditFile(pathlib.Path.home() / '.sjef/molpro/backends.xml')
        self.backend_configuration_editor.setMinimumSize(600, 400)
        self.backend_configuration_editor.show()

    def edit_input_structure(self):
        f = self.geometry_files()
        if f:
            filename = self.project.filename('', f[-1][1], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            self.embedded_builder(filename)

    def refresh_output_tabs(self):
        if len(self.output_tabs) != len(
                [suffix for suffix, pane in self.output_panes.items() if
                 os.path.exists(self.project.filename(suffix))]) + (1 if self.vod else 0):
            self.output_tabs.clear()
            for suffix, pane in self.output_panes.items():
                if os.path.exists(self.project.filename(suffix)):
                    self.output_tabs.addTab(pane, suffix)
            if self.vod:
                self.output_tabs.addTab(self.vod, 'structure')

    def guided_toggle(self):
        self.refresh_input_tabs(index=1 if self.guided_action.isChecked() else 0)

    def refresh_input_tabs(self, index=0):
        input_text = self.input_pane.toPlainText()
        if not input_text: input_text = ''
        input_specification = molpro_input.parse(input_text)
        guided = molpro_input.equivalent(input_text, input_specification)
        if not guided and index == 1:
            box = QMessageBox()
            box.setText('Guided mode cannot be used because the input is too complex')
            box.exec()
            self.guided_action.setChecked(False)
        if len(self.input_tabs) < 1:
            self.input_tabs.addTab(self.input_pane, 'freehand')
        if not guided and len(self.input_tabs) != 1:
            self.input_tabs.removeTab(1)
        if guided and len(self.input_tabs) != 2:
            self.guided_pane = QLabel()
            self.input_tabs.addTab(self.guided_pane, 'guided')
        self.input_tabs.setCurrentIndex(
            index if index >= 0 and index < len(self.input_tabs) else len(self.input_tabs) - 1)
        if guided and self.input_tabs.currentIndex() == 1:
            self.guided_pane.setText(
                re.sub('}$', '\n}', re.sub('^{', '{\n  ', str(input_specification))).replace(', ', ',\n  '))

    def vod_selector_action(self):
        text = self.vod_selector.currentText().strip()
        if text == '':
            return
        elif text == 'None':
            if self.vod:
                index = self.output_tabs.indexOf(self.vod)
                if index >= 0: self.output_tabs.removeTab(index)
                self.vod = None
        elif text[:5] == 'Edit ':
            filename = self.project.filename('', text[5:], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            self.embedded_builder(filename)
        elif text == 'Input':
            self.visualise_input()
        elif text == 'Output':
            self.visualise_output(False, 'xml')
        else:
            self.visualise_output(False, '', text)

    def rebuild_vod_selector(self):
        self.vod_selector.clear()
        self.vod_selector.addItem('None')
        for t, f in self.geometry_files():
            self.vod_selector.addItem('Edit ' + f)
        self.vod_selector.addItem('Input')
        if self.project.status == 'completed' or (
                os.path.isfile(self.project.filename('xml')) and open(self.project.filename('xml'),
                                                                      'r').read().rstrip()[
                                                                 -9:] == '</molpro>'):
            self.vod_selector.addItem('Output')
            for t, f in self.putfiles():
                self.vod_selector.addItem(f)

    def putfiles(self):
        result = []
        lines = self.input_pane.toPlainText().replace(';', '\n').split('\n')
        for line in lines:
            fields = line.replace(' ', ',').split(',')
            if len(fields) > 2 and fields[0].lower() == 'put':
                result.append((fields[1], fields[2]))
        return result

    def geometry_files(self):
        import re
        result = []
        lines = self.input_pane.toPlainText().replace(';', '\n').split('\n')
        for line in lines:
            fields = line.replace(' ', ',').split(',')
            regex = r'geometry=([-@#&a-z0-9_]+)\.(xyz)'
            if len(fields) == 1 and re.match(regex, fields[0], re.IGNORECASE):
                result.append(
                    (re.sub(regex, r'\2', fields[0]), re.sub(regex, r'\1.\2', fields[0], flags=re.IGNORECASE)))
        return result

    def run(self):
        self.project.run()

    def kill(self):
        self.project.kill()

    def clean(self):
        self.project.clean()

    def visualise_output(self, param, typ='xml', name=None):
        if name:
            self.embedded_vod(self.project.filename(typ, name), command='mo HOMO')
        else:
            self.embedded_vod(self.project.filename(typ), command='mo HOMO')

    def embedded_vod(self, file, command='', **kwargs):
        firstmodel = 1
        try:
            vibs = factory_vibration_set(file, **kwargs)
            firstmodel = firstvib = vibs.coordinateSet
        except (IndexError, KeyError):
            vibs = None
        try:
            orbs = factory_orbital_set(file, **kwargs)
            firstmodel = firstorb = orbs.coordinateSet
        except (IndexError, KeyError):
            orbs = None
        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src=" """ + self.jsmol_min_js + """"> </script>
</head>
<body>
<table>
<tr valign="top"><td>
<script>
var Info = {
  color: "#FFFFFF",
  height: 400,
  width: 400,
  script: "load '""" + file + """'; set antialiasDisplay ON; set showFrank OFF; model """ + str(
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
        self.add_vod(html, **kwargs)

    def embedded_builder(self, file, **kwargs):

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src=" """ + self.jsmol_min_js + """"> </script>
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
        html += ' load \'' + file + '\';'
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

        self.add_vod(html, **kwargs)

    def add_vod(self, html, width=400, height=420, verbosity=0):
        if verbosity:
            print(html)
            open('test.html', 'w').write(html)
        webview = QWebEngineView()
        profile = QWebEngineProfile()
        self.webengine_profiles.append(
            profile)  # FIXME This to avoid premature garbage collection. A resource leak. Need to find a way to delete the previous QWebEnginePage instead
        profile.downloadRequested.connect(self._download_requested)
        page = QWebEnginePage(profile, webview)
        page.setHtml(html, QUrl.fromLocalFile(str(pathlib.Path(__file__).resolve())))
        webview.setPage(page)

        webview.setMinimumSize(width, height)
        if not self.vod:
            # self.layout.addWidget(webview)
            self.output_tabs.addTab(webview, 'structure')
        else:
            # self.layout.replaceWidget(self.vod, webview)
            self.output_tabs.removeTab(self.output_tabs.indexOf(self.vod))
            self.output_tabs.addTab(webview, 'structure')
        self.vod = webview
        self.vod.show()
        self.output_tabs.setCurrentIndex(self.output_tabs.indexOf(self.vod))

    def _download_requested(self, item):
        import re
        if item.downloadFileName():
            item.setDownloadFileName(re.sub(r' \(\d+\)\.', r'.', item.downloadFileName()))
            item.setDownloadDirectory(self.project.filename(run=-1))
            item.accept()

    def visualise_input(self, param=False):
        import tempfile
        geometry_directory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometry_directory.mkdir(exist_ok=True)
        xyz_file = str(geometry_directory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        if not os.path.isfile(xyz_file) or os.path.getmtime(xyz_file) < os.path.getmtime(
                self.project.filename('inp', run=-1)) or any(
            [os.path.getmtime(xyz_file) < os.path.getmtime(self.project.filename('', gfile[1], run=-1)) for gfile in
             self.geometry_files()]):
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
                with open(xyz_file, 'w') as f:
                    f.write(str(len(geometry)) + '\n\n')
                    for atom in geometry:
                        f.write(atom['elementType'])
                        for c in atom['xyz']: f.write(' ' + str(c * .529177210903))
                        f.write('\n')
        self.embedded_vod(xyz_file, command='')

    def closeEvent(self, a0):
        self.close_signal.emit(self)

    def newAction(self):
        self.new_signal.emit(self)

    def chooserOpen(self):
        self.chooser_signal.emit(self)

    def clean(self):
        self.project.clean(1)

    def import_file(self):
        _dir = settings['import_directory'] if 'import_directory' in settings else os.path.dirname(
            self.project.filename(run=-1))
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Import file(s) into project', _dir)
        for filename in filenames:
            if os.path.isfile(filename):
                settings['import_directory'] = os.path.dirname(filename)
                self.project.import_file(filename)

    def import_structure(self):
        _dir = settings['geometry_directory'] if 'geometry_directory' in settings else (
            settings['import_directory'] if 'import_directory' in settings else os.path.dirname(
                self.project.filename(run=-1)))
        filename, junk = QFileDialog.getOpenFileName(self, 'Import xyz file into project', _dir)
        if os.path.isfile(filename):
            settings['geometry_directory'] = os.path.dirname(filename)
            self.adoptStructureFile(filename)

    def adoptStructureFile(self, filename):
        if os.path.exists(filename):
            self.project.import_file(filename)
            text = self.input_pane.toPlainText()
            if re.match('^ *geometry *= *[/a-z0-9].*', text, flags=re.IGNORECASE):
                self.input_pane.setPlainText(
                    re.sub('^ *geometry *=.*[\n;]', 'geometry=' + os.path.basename(filename) + '\n', text))
                self.rebuild_vod_selector()
            else:
                self.input_pane.setPlainText('geometry=' + os.path.basename(filename) + '\n' + text)

    def databaseImportStructure(self):
        if (filename := database_choose_structure()):
            self.adoptStructureFile(filename)
            os.remove(filename)
            os.rmdir(os.path.dirname(filename))
            self.edit_input_structure()

    def import_input(self):
        _dir = settings['import_directory'] if 'import_directory' in settings else os.path.dirname(
            self.project.filename(run=-1))
        filename, junk = QFileDialog.getOpenFileName(self, 'Copy file to project input', _dir)
        if os.path.isfile(filename):
            settings['import_directory'] = os.path.dirname(filename)
            self.project.import_input(filename)

    def export_file(self):
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Export file(s) from the project',
                                                       self.project.filename(run=-1))
        for filename in filenames:
            if os.path.isfile(filename):
                b = os.path.basename(filename)
                _dir = settings['export_directory'] if 'export_directory' in settings else os.path.dirname(
                    self.project.filename())
                dest = QFileDialog.getExistingDirectory(self, 'Destination for ' + b, _dir)
                if dest:
                    settings['export_directory'] = dest
                    shutil.copy(filename, dest)

    def browse_project(self):
        dlg = QFileDialog(self, self.project.filename(), self.project.filename(run=-1))
        dlg.setLabelText(QFileDialog.Accept, "OK")
        dlg.exec()
