import concurrent.futures
import difflib
import os
import pathlib
import shutil
import subprocess
import sys
import re

from PyQt5.QtCore import QTimer, pyqtSignal, QUrl, QCoreApplication, Qt, QEvent
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QMessageBox, QTabWidget, QFileDialog, QDialogButtonBox, QFormLayout, QLineEdit, \
    QSplitter, QMenu
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


class webEngineView(QWebEngineView):
    def __init__(self):
        super().__init__()
    #     self.installEventFilter(self)
    #
    # def eventFilter(self, obj, event):
    #     if (event.type() == QEvent.Resize):
    #         print('webEngineView resize event received', self.geometry(), self.geometry().width(), self.geometry().height())
    #     return super().eventFilter(obj, event)


class ProjectWindow(QMainWindow):
    close_signal = pyqtSignal(QWidget)
    new_signal = pyqtSignal(QWidget)
    chooser_signal = pyqtSignal(QWidget)
    vod = None
    trace = settings['ProjectWindow_debug'] if 'ProjectWindow_debug' in settings else 0
    KD_debug = settings['KD_debug'] if 'KD_debug' in settings else 0

    def __init__(self, filename, window_manager, latency=1000):
        super().__init__()
        self.window_manager = window_manager
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

        assert filename is not None
        self.project = Project(filename)
        # print(self.project.registry())
        # print(self.project.registry('PLUGIN'))
        # print(self.project.registry('RO')['TRUNC']['default_value'])
        # print(self.project.registry('commandset').keys())
        # print(self.project.registry('commandset')['CCSD'])
        # print(self.project.procedures_registry())
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

        self.discover_external_viewer_commands()

        self.input_pane = EditFile(self.project.filename('inp', run=-1), latency)
        if self.input_pane.toPlainText().strip('\n ') == '':
            self.input_pane.setPlainText(
                'geometry={0}.xyz\nbasis=cc-pVTZ-PP\nrhf'.format(os.path.basename(self.project.name).replace(' ', '-')))
        self.setWindowTitle(filename)

        self.output_panes = {
            suffix: ViewProjectOutput(self.project, suffix) for suffix in ['out', 'log']}

        self.webengine_profiles = []

        try:
            self.whole_of_procedures_registry = self.project.procedures_registry()
        except Exception as e:
            msg = QMessageBox()
            msg.setText('Error in finding local molpro')
            msg.setDetailedText('Guided mode will not work correctly\r\n' + str(type(e)))
            msg.exec()
            self.whole_of_procedures_registry = {}
        self.setup_menubar()

        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_action.trigger)
        self.run_button.setToolTip("Run the job")

        self.statusBar = StatusBar(self.project, [self.run_action, self.run_button], [self.kill_action])
        self.statusBar.refresh()

        left_layout = QVBoxLayout()
        self.input_tabs = QTabWidget()
        self.input_pane.textChanged.connect(lambda: self.thread_executor.submit(self.input_text_changed_consequence))
        self.input_tabs.setTabBarAutoHide(True)
        self.input_tabs.setDocumentMode(True)
        self.input_tabs.setTabPosition(QTabWidget.South)
        self.input_tabs.currentChanged.connect(self.input_tab_changed_consequence)
        left_layout.addWidget(self.input_tabs)
        self.input_tabs.setMinimumHeight(300)
        self.input_tabs.setMinimumWidth(300)
        self.statusBar.setMaximumWidth(400)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.run_button)
        # button_layout.addWidget(self.killButton)
        self.vod_selector = QComboBox()
        vod_select_layout = QFormLayout()
        button_layout.addLayout(vod_select_layout)
        vod_select_layout.addRow('Structure display:', self.vod_selector)
        # self.external_selector = QComboBox()
        # self.external_selector.addItem('embedded')
        # self.external_selector.addItems(self.external_viewer_commands.keys())
        # self.external_selector.currentTextChanged.connect(self.vod_external_launch)
        # vod_select_layout.addRow('View in', self.external_selector)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(self.statusBar)
        self.input_tabs.addTab(self.input_pane, 'freehand')
        self.input_text_changed_consequence(0)
        self.input_tabs.setCurrentIndex(1)
        self.guided_action.setChecked(self.input_tabs.currentIndex() == 1)

        top_layout = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(splitter)

        left_widget = QWidget(self)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)
        self.output_tabs = QTabWidget(self)
        self.output_tabs.setTabBarAutoHide(True)
        self.output_tabs.setDocumentMode(True)
        self.output_tabs.setTabPosition(QTabWidget.South)
        self.refresh_output_tabs()
        self.timer_output_tabs = QTimer()
        self.timer_output_tabs.timeout.connect(self.refresh_output_tabs)
        self.timer_output_tabs.start(2000)
        splitter.addWidget(self.output_tabs)
        splitter.setStretchFactor(1, 2147483647)

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
        # self.installEventFilter(self)

    # def eventFilter(self, obj, event):
    #     if (event.type() == QEvent.Resize):
    #         print('resize event received', self.geometry(), self.geometry().width(), self.geometry().height())
    #         if self.output_tabs:
    #             print('output_tabs size', self.output_tabs.geometry())
    #         if self.input_tabs:
    #             print('input_tabs size', self.input_tabs.geometry())
    #         if self.vod:
    #             print('vod size', self.vod.geometry())
    #     return super().eventFilter(obj, event)

    def discover_external_viewer_commands(self):
        external_command_stems = [
            'avogadro',
            'Avogadro2',
            'jmol',
        ]
        external_command_paths = []
        if 'PATH' in os.environ:
            external_command_paths += os.environ['PATH'].split(':')
        # TODO paths for Windows
        external_command_paths += [
            '/Applications/Avogadro.app/Contents/MacOS',
            '/Applications/Avogadro2.app/Contents/MacOS',
            '/usr/local/bin',
            '/usr/bin',
            '/bin',
        ]
        self.external_viewer_commands = {}
        for command in external_command_stems:
            for path in external_command_paths:
                if os.path.exists(pathlib.Path(path) / command):
                    self.external_viewer_commands[command] = str(pathlib.Path(path) / command)
                    break

    def setup_menubar(self):
        menubar = MenuBar(self)
        self.setMenuBar(menubar)
        menubar.addAction('New', 'Projects', slot=self.newAction, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addAction('Close', 'Projects', self.close, 'Ctrl+W')
        menubar.addAction('Open', 'Projects', self.chooserOpen, 'Ctrl+O', 'Open another project')
        menubar.addSeparator('Projects')
        self.recent_menu = RecentMenu(self.window_manager)
        menubar.addSubmenu(self.recent_menu, 'Projects')
        menubar.addSeparator('Projects')
        menubar.addAction('Move to...', 'Projects', self.move_to, tooltip='Move the project')
        menubar.addAction('Copy to...', 'Projects', self.copy_to, tooltip='Make a copy of the project')
        # menubar.addAction('Erase', 'Projects', self.erase, tooltip='Completely erase the project') # TODO get erase() working
        menubar.addSeparator('Projects')
        menubar.addAction('Quit', 'Projects', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')
        menubar.addAction('Import input', 'Files', self.import_input, 'Ctrl+Shift+I',
                          tooltip='Import a file and assign it as the input for the project')
        menubar.addAction('Import structure', 'Files', self.import_structure, 'Ctrl+Alt+I',
                          tooltip='Import an xyz file and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Search external databases for structure', 'Files', self.databaseImportStructure,
                          'Ctrl+Shift+Alt+I',
                          tooltip='Search PubChem and ChemSpider for a molecule and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Import file', 'Files', self.import_file, 'Ctrl+I',
                          tooltip='Import one or more files, eg geometry definition, into the project')
        menubar.addAction('Export file', 'Files', self.export_file, 'Ctrl+E',
                          tooltip='Export one or more files from the project')
        menubar.addAction('Clean', 'Files', self.clean, tooltip='Remove old runs from the project')
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
        menubar.addAction('Show parsed input specification', 'Edit', self.show_input_specification, 'Shift+Ctrl+G')

        menubar.addSeparator('Files')
        menubar.addAction('Browse project folder', 'Files', self.browse_project, 'Ctrl+Alt+F',
                          tooltip='Look at the contents of the project folder.  With care, files can be edited or renamed, but note that this may break the integrity of the project.')
        menubar.addAction('Zoom In', 'View', lambda: [p.zoomIn() for p in self.output_panes.values()], 'Alt+Shift+=',
                          'Increase font size')
        menubar.addAction('Zoom Out', 'View', lambda: [p.zoomOut() for p in self.output_panes.values()], 'Alt+-',
                          'Decrease font size')
        menubar.addSeparator('View')
        menubar.addAction('Input structure', 'View', self.visualise_input,
                          tooltip='View the molecular structure in the job input')
        menubar.addAction('Output structure', 'View', self.visualise_output, 'Alt+D',
                          tooltip='View the molecular structure at the end of the job')
        if self.external_viewer_commands:
            self.external_menu = QMenu('View molecule in external program...')
            for command in self.external_viewer_commands.keys():
                action = self.external_menu.addAction(command)
                action.triggered.connect(lambda dum, command=command: self.vod_external_launch(command))

            menubar.addSubmenu(self.external_menu, 'View')
        menubar.addSeparator('View')
        menubar.addAction('Next output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() + 1) % len(self.output_tabs)), 'Alt+]')
        menubar.addAction('Previous output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() + 1) % len(self.output_tabs)), 'Alt+[')

        self.run_action = menubar.addAction('Run', 'Job', self.run, 'Ctrl+R', 'Run Molpro on the project input')
        self.run_force_action = menubar.addAction('Run (force)', 'Job', self.run_force, 'Ctrl+Shift+R',
                                                  'Run Molpro on the project input, even if the input has not changed since the last run')
        self.kill_action = menubar.addAction('Kill', 'Job', self.kill, tooltip='Kill the running job')
        menubar.addAction('Backend', 'Job', lambda: configure_backend(self), 'Ctrl+B', 'Configure backend')
        menubar.addAction('Edit backend configuration file', 'Job', self.edit_backend_configuration, 'Ctrl+Shift+B',
                          'Edit backend configuration file')
        help_manager = HelpManager(menubar)
        help_manager.register('Overview', 'README')
        help_manager.register('Another', 'something else')
        help_manager.register('Backends', 'doc/backends.md')
        menubar.show()

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
        if self.trace: print('guided_toggle')
        index = 1 if self.guided_action.isChecked() else 0
        guided = self.guided_possible()
        if not guided and index == 1:
            box = QMessageBox()
            box.setText('Guided mode cannot be used because the input is too complex')
            spec_input = molpro_input.canonicalise(molpro_input.create_input(self.input_specification))
            file_input = molpro_input.canonicalise(self.input_pane.toPlainText())
            box.setInformativeText(
                'The input regenerated from the attempt to parse into guided mode is\n' +
                spec_input + '\n\nThe input file in canonical form is\n' + file_input + '\n\nDifferences:\n' +
                '\n'.join(list(
                    difflib.context_diff(spec_input.split('\n'), file_input.split('\n'),
                                         fromfile='parsed specification',
                                         tofile='input file'))))
            box.exec()
            self.guided_action.setChecked(False)
        else:
            self.input_tabs.setCurrentIndex(index)

    def input_text_changed_consequence(self, index=0):
        if self.trace: print('input_text_changed_consequence, index=', index)
        guided = self.guided_possible()
        if not guided and len(self.input_tabs) != 1:
            self.input_tabs.removeTab(1)
        if guided and len(self.input_tabs) < 2:
            self.setup_guided_pane()

    def guided_possible(self):
        input_text = self.input_pane.toPlainText()
        if not input_text: input_text = ''
        self.input_specification = molpro_input.parse(input_text, self.allowed_methods())
        guided = molpro_input.equivalent(input_text, self.input_specification)
        return guided

    def input_tab_changed_consequence(self, index=0):
        if self.trace: print('input_tab_changed_consequence, index=', index, self.input_tabs.currentIndex())
        if self.input_tabs.currentIndex() == 1:
            self.refresh_guided_pane()

    def setup_guided_pane(self):
        self.guided_pane = QWidget()
        self.input_tabs.addTab(self.guided_pane, 'guided')
        self.guided_layout = QVBoxLayout()
        self.guided_pane.setLayout(self.guided_layout)
        guided_form = QFormLayout()

        self.guided_combo_orientation = QComboBox()
        self.guided_combo_orientation.addItems(molpro_input.orientation_options.keys())
        guided_form.addRow('Orientation', self.guided_combo_orientation)
        self.guided_combo_orientation.currentTextChanged.connect(lambda text: self.input_specification_change('orientation', text))

        textLabel_wave_fct_char = QLabel()
        textLabel_wave_fct_char.setText("Wave Function Characteristics:")
        self.guided_layout.addWidget(textLabel_wave_fct_char)

        self.guided_combo_wave_fct_symm = QComboBox()
        self.guided_combo_wave_fct_symm.addItems(molpro_input.wave_fct_symm_commands.keys())
        guided_form.addRow('Wave function symmetry', self.guided_combo_wave_fct_symm)
        self.guided_combo_wave_fct_symm.currentTextChanged.connect(lambda text: self.input_specification_change('wave_fct_symm', text))


        textLabel_calculation = QLabel()
        textLabel_calculation.setText("Calculation:")
        self.guided_layout.addWidget(textLabel_calculation)

        self.guided_combo_job_type = QComboBox()
        self.guided_combo_job_type.setMaximumWidth(180)
        self.guided_combo_job_type.addItems(molpro_input.job_type_commands.keys())
        guided_form.addRow('Type', self.guided_combo_job_type)
        self.guided_combo_job_type.currentTextChanged.connect(lambda text: self.input_specification_change('job_type', text))

        self.guided_combo_method = QComboBox()
        # print(self.project.registry('commandset').keys())

        self.guided_combo_method.addItems(self.allowed_methods())
        guided_form.addRow('Method', self.guided_combo_method)
        self.guided_combo_method.currentTextChanged.connect(lambda text: self.input_specification_change('method', text))
        self.guided_layout.addLayout(guided_form)
        self.guided_basis_input = QLineEdit()
        self.guided_basis_input.setMinimumWidth(200)
        guided_form.addRow('Basis set', self.guided_basis_input)
        self.guided_basis_input.textChanged.connect(lambda text: self.input_specification_change('basis', text))

    def refresh_guided_pane(self):
        if self.trace: print('refresh_guided_pane')
        self.guided_combo_orientation.setCurrentText(
            self.input_specification['orientation'] if 'orientation' in self.input_specification else
            list(molpro_input.orientation_options.keys())[0])
        self.guided_combo_wave_fct_symm.setCurrentText(
            self.input_specification['wave_fct_symm'] if 'wave_fct_symm' in self.input_specification else
            list(molpro_input.wave_fct_symm_commands.keys())[0])
        if 'method' in self.input_specification:
            base_method = re.sub('[a-z]+-', '', self.input_specification['method'], flags=re.IGNORECASE)
            prefix = re.sub('-.*', '', self.input_specification['method']) if base_method != self.input_specification[
                'method'] else None
            method_index = self.guided_combo_method.findText(base_method, Qt.MatchFixedString)
            if self.KD_debug: print('KD Debug, index=', method_index, 'method=',
                                 self.input_specification['method'], 'base_method=', base_method, 'prefix=',
                                 prefix)
            self.guided_combo_method.setCurrentIndex(method_index)
        if 'basis' in self.input_specification:
            self.guided_basis_input.setText(self.input_specification['basis'])
        if 'job_type' in self.input_specification:
            self.guided_combo_job_type.setCurrentText(self.input_specification['job_type'])

    def input_specification_change(self, key, value):
        self.input_specification[key] = value
        self.refresh_input_from_specification()

    def allowed_methods(self):
        result = []
        if self.whole_of_procedures_registry is None:
            self.whole_of_procedures_registry = self.project.procedures_registry()
        for keyfound in self.whole_of_procedures_registry.keys():
            if self.whole_of_procedures_registry[keyfound]['class'] == 'PROG':
                result.append(self.whole_of_procedures_registry[keyfound]['name'])
        return result

    def refresh_input_from_specification(self):
        if self.trace: print('refresh_input_from_specification')
        current_tab = self.input_tabs.currentIndex()
        new_input = molpro_input.create_input(self.input_specification)
        if not molpro_input.equivalent(self.input_pane.toPlainText(), new_input):
            self.input_pane.setPlainText(new_input)

    def vod_external_launch(self, command=''):
        if command and command != 'embedded':
            self.vod_selector_action(external_path=self.external_viewer_commands[command], force=True)

    def vod_selector_action(self, text1=None, external_path=None, force=False):
        if force and self.vod_selector.currentText().strip() == 'None':
            self.vod_selector.setCurrentText('Output')
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
            if external_path:
                subprocess.Popen([external_path, filename])
            else:
                self.embedded_builder(filename)
        elif text == 'Input':
            self.visualise_input(external_path=external_path)
        elif text == 'Output':
            self.visualise_output(external_path, 'xml')
        else:
            self.visualise_output(external_path, '', text)

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

    def run_force(self):
        self.project.run(force=True)

    def kill(self):
        self.project.kill()

    def clean(self):
        self.project.clean()

    def visualise_output(self, external_path=None, typ='xml', name=None):
        filename = self.project.filename(typ, name) if name else self.project.filename(typ)
        if external_path:
            subprocess.Popen([external_path, filename])
        else:
            self.embedded_vod(filename, command='mo HOMO')

    def embedded_vod(self, file, command='', **kwargs):
        width = self.output_tabs.geometry().width() - 310
        height = self.output_tabs.geometry().height() - 40
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
  height: """ + str(height) + """,
  width: """ + str(width) + """,
  script: "load '""" + re.sub('\\\\', '\\\\\\\\',
                              file) + """'; set antialiasDisplay ON; set showFrank OFF; model """ + str(
            firstmodel) + """; """ + command + """; mo nomesh fill translucent 0.3; mo resolution 7; mo titleFormat ' '",
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


 var r = [
    ["mo resolution 4","Very coarse",true],
    ["mo resolution 7","Coarse",true],
    ["mo resolution 10","Medium"],
    ["mo resolution 13","Fine"],
    ["mo resolution 16","Very fine"]
 ];
 Jmol.jmolHtml("Resolution:<br>")
 Jmol.jmolRadioGroup(myJmol, r, "<br>", "Resolution");

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
        width = self.output_tabs.geometry().width() - 310
        height = self.output_tabs.geometry().height() - 40

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
  height: """ + str(height) + """,
  width: """ + str(width) + """,
  script: "set antialiasDisplay ON;"""
        html += ' load \'' + re.sub('\\\\', '\\\\', file) + '\';'
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

    def add_vod(self, html, width=800, height=420, verbosity=0):
        if verbosity:
            print(html)
            open('test.html', 'w').write(html)
        webview = webEngineView()
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

    def visualise_input(self, param=False, external_path=None):
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
        if external_path:
            subprocess.Popen([external_path, xyz_file])
        else:
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
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Import file(s) into project',
                                                       str(pathlib.Path(_dir) / '*'),
                                                       options=QFileDialog.DontResolveSymlinks)
        for filename in filenames:
            if os.path.isfile(filename):
                settings['import_directory'] = os.path.dirname(filename)
                self.project.import_file(filename)

    def import_structure(self):
        _dir = settings['geometry_directory'] if 'geometry_directory' in settings else (
            settings['import_directory'] if 'import_directory' in settings else os.path.dirname(
                self.project.filename(run=-1)))
        filename, junk = QFileDialog.getOpenFileName(self, 'Import xyz file into project',
                                                     str(pathlib.Path(_dir) / '*'),
                                                     options=QFileDialog.DontResolveSymlinks)
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
        filename, junk = QFileDialog.getOpenFileName(self, 'Copy file to project input', str(pathlib.Path(_dir) / '*'),
                                                     options=QFileDialog.DontResolveSymlinks)
        if os.path.isfile(filename):
            settings['import_directory'] = os.path.dirname(filename)
            self.project.import_input(filename)

    def export_file(self):
        filenames, junk = QFileDialog.getOpenFileNames(self, 'Export file(s) from the project',
                                                       str(pathlib.Path(self.project.filename()) / '*'))
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
        dlg = QFileDialog(self, self.project.filename(), str(pathlib.Path(self.project.filename(run=-1)) / '*'))
        dlg.setLabelText(QFileDialog.Accept, "OK")
        dlg.exec()

    def move_to(self):
        file_name, filter = QFileDialog.getSaveFileName(self, 'Move project to...',
                                                        os.path.dirname(self.project.filename(run=-1)),
                                                        'Molpro project (*.molpro)', )
        if file_name:
            self.project.move(file_name)
            self.window_manager.register(ProjectWindow(file_name, self.window_manager))
            self.close()

    def copy_to(self):
        file_name, filter = QFileDialog.getSaveFileName(self, 'Copy project to...',
                                                        os.path.dirname(self.project.filename(run=-1)),
                                                        'Molpro project (*.molpro)', )
        if file_name:
            self.project.copy(file_name, keep_run_directories=0)
            return file_name

    def erase(self):
        result = QMessageBox.question(self, 'Erase project',
                                      'Are you sure you want to erase project ' + self.project.filename(run=-1))
        if result == QMessageBox.Yes:
            QMessageBox.information('Erasing of projects is not yet implemented')
            return
            print('erasing ', self.project.filename(run=-1))
            self.window_manager.erase(self)
            return
            del self.statusBar
            shutil.rmtree(self.project.filename(run=-1))
            del self
            return
            # self.project.erase()
            self.close()

    def show_input_specification(self):
        QMessageBox.information(self, 'Input specification', 'Input specification:\r\n' +
                                re.sub('}$', '\n}', re.sub('^{', '{\n  ', str(self.input_specification))).replace(', ',
                                                                                                                  ',\n  '))
