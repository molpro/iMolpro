import concurrent.futures
import difflib
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import re
import platform

from PyQt5.QtCore import QTimer, pyqtSignal, QUrl, QCoreApplication, Qt, QSize
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QMessageBox, QTabWidget, QFileDialog, QFormLayout, QLineEdit, \
    QSplitter, QMenu, QGridLayout, QInputDialog, QCheckBox, QApplication, QToolButton
from PyQt5.QtGui import QIntValidator, QFont
from pymolpro import Project

import molpro_input
from SpinComboBox import SpinComboBox
from molpro_input import InputSpecification
from CheckableComboBox import CheckableComboBox
from MenuBar import MenuBar
from OldOutputMenu import OldOutputMenu
from RecentMenu import RecentMenu
from database import database_choose_structure
from help import HelpManager
from utilities import EditFile, ViewFile, factory_vibration_set, factory_orbital_set
from backend import configure_backend, BackendConfigurationEditor
from settings import settings, settings_edit
from OptionsDialog import OptionsDialog


class StatusBar(QLabel):
    def __init__(self, project: Project, run_actions: list, kill_actions: list, latency=1000):
        super().__init__()
        self.project = project
        self.run_actions = run_actions
        self.kill_actions = kill_actions
        self.refresh_timer = QTimer(self)
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
    def __init__(self, project, suffix='out', width=132, latency=100, filename_latency=500, point_size=8, instance=0):
        self.project = project
        self.suffix = suffix
        self.instance = -1 if suffix == 'inp' else instance
        minimum_point_size = point_size - 2
        self.character_width = width
        super().__init__(self.project.filename(suffix, run=self.instance), latency=latency, point_size=point_size)
        target_width = self.fontMetrics().size(0, ''.join(['M' for k in range(width)])).width()
        self.setFont(QFont(self.font().family(), minimum_point_size))
        minimum_width = self.fontMetrics().size(0, ''.join(['M' for k in range(width)])).width()
        super().setMinimumWidth(minimum_width)
        self.resize(target_width, 900)
        # self.resize(target_width, self.minimumHeight())
        self.refresh_output_file_timer = QTimer(self)
        self.refresh_output_file_timer.timeout.connect(self.refresh_output_file)
        self.refresh_output_file_timer.start(filename_latency)  # find a better way

    def refresh_output_file(self):
        latest_filename = self.project.filename(self.suffix, run=self.instance)
        if latest_filename != self.filename:
            self.reset(latest_filename)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        contingency = 4
        for size in range(100, 1, -1):
            self.setFont(QFont(self.font().family(), size))
            f_metrics = self.fontMetrics()
            if f_metrics.size(0,
                              ''.join(['M' for k in range(
                                  self.character_width)])).width() + contingency < self.size().width():
                break


class ProjectWindow(QMainWindow):
    close_signal = pyqtSignal(QWidget, name='closeSignal')
    new_signal = pyqtSignal(QWidget, name='newSignal')
    chooser_signal = pyqtSignal(QWidget, name='chooserSignal')
    trace = settings['ProjectWindow_debug'] if 'ProjectWindow_debug' in settings else 0
    null_prompt = '- Select -'
    all_qualities = 'All Qualities'
    basis_qualities = [all_qualities, 'SZ', 'DZ', 'TZ', 'QZ', '5Z', '6Z']

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # print('ProjectWindow.resizeEvent', self.size())
        settings['project_window_width'] = self.size().width()
        settings['project_window_height'] = self.size().height()

    def __init__(self, filename, window_manager, latency=1000):
        super().__init__(None)
        self.window_manager = window_manager
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.initialised_from_input = False

        assert filename is not None
        try:
            self.project = Project(filename)
        except Exception as e:
            msg = QMessageBox()
            msg.setText('Project ' + filename + ' cannot be opened')
            msg.setDetailedText(str(e))
            msg.exec()
            self.invalid = True
            return

        settings['project_directory'] = os.path.dirname(self.project.filename(run=-1))

        # print('platform',platform.uname().system)
        # print('PATH', os.environ['PATH'])
        try:
            if platform.uname().system == 'Windows':
                os.environ['PATH'] = os.path.dirname(os.path.abspath(__file__))+ ';' + os.environ['PATH']
                # print('PATH',os.environ['PATH'])
            elif 'PATH' in os.environ and 'SHELL' in os.environ:
                    os.environ['PATH'] = os.popen(os.environ['SHELL'] + " -l -c 'echo $PATH'").read() + ':' + os.environ[
                'PATH']  # make PATH just as if running from shell
        except Exception as e:
            msg = QMessageBox()
            msg.setText('Error in setting PATH')
            msg.setDetailedText(str(e))
            msg.exec()
        # print('PATH', os.environ['PATH'])
        self.jsmol_min_js = str(pathlib.Path(__file__).parent / "JSmol.min.js")
        if hasattr(sys, '_MEIPASS') and platform.uname().system != 'Windows':
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
        self.setWindowTitle(filename)

        molpro_input.supported_methods = self.allowed_methods()
        self.input_specification = InputSpecification(self.input_pane.toPlainText(), directory=self.project.filename())

        self.output_panes = {
            suffix: ViewProjectOutput(self.project, suffix, point_size=12 if suffix == 'inp' else 9,
                                      width=80 if suffix == 'inp' else 132) for suffix in
            [
                'out',
                'log',
                'inp'
            ]}

        self.vods = {}
        self.setup_menubar()

        self.run_button = QPushButton('Run job')
        self.run_button.clicked.connect(self.run_action.trigger)
        self.run_button.setToolTip("Run the job")

        self.statusBar = StatusBar(self.project, [self.run_action, self.run_button], [self.kill_action])
        self.statusBar.refresh()

        left_layout = QVBoxLayout()
        self.input_tabs = QTabWidget(self)
        self.input_pane.textChanged.connect(lambda: self.thread_executor.submit(self.input_text_changed_consequence))
        self.input_tabs.setTabBarAutoHide(True)
        self.input_tabs.setDocumentMode(True)
        self.input_tabs.setTabPosition(QTabWidget.South)
        self.input_tabs.currentChanged.connect(self.input_tab_changed_consequence)
        left_layout.addWidget(self.input_tabs)
        self.input_tabs.setMinimumHeight(300)
        self.input_tabs.setMinimumWidth(400)
        self.statusBar.setMaximumWidth(400)
        button_layout = QHBoxLayout()
        # left_layout.addWidget(QLabel('Execution:'))
        left_layout.addLayout(button_layout)
        self.backend_selector = QComboBox(self)
        self.backend_selector.setMinimumWidth(15)
        self.backend_selector.addItems(self.project.backend_names())
        backend = self.project.property_get('backend')
        self.backend_selector.setCurrentText(backend['backend'] if backend else 'local')
        self.backend_selector.currentTextChanged.connect(lambda text: self.project.property_set({'backend': text}))
        self.backend_parameter_button = QPushButton('Parameters')
        self.backend_parameter_button.clicked.connect(lambda: configure_backend(self))
        backend_label = QLabel('Backend:')
        button_layout.addWidget(backend_label)
        button_layout.addWidget(self.backend_selector)
        button_layout.addWidget(self.backend_parameter_button)
        backend_label.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')
        self.backend_selector.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')
        self.backend_parameter_button.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')
        button_layout.addWidget(self.run_button)
        self.run_button.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() + 2) + 'pt;')
        left_layout.addWidget(self.statusBar)
        self.input_tabs.addTab(self.input_pane, 'freehand')
        self.guided_pane = GuidedPane(self)
        self.input_tabs.addTab(self.guided_pane, 'guided')
        self.input_tabs.setTabVisible(self.input_tabs.indexOf(self.guided_pane), False)
        self.input_text_changed_consequence(0)

        top_layout = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(splitter)

        left_widget = QWidget(self)
        left_widget.setContentsMargins(0, 0, 0, 0)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)
        self.output_tabs = QTabWidget(self)
        self.output_tabs.setTabBarAutoHide(True)
        self.output_tabs.setDocumentMode(True)
        self.output_tabs.setTabPosition(QTabWidget.South)
        self.refresh_output_tabs()
        self.timer_output_tabs = QTimer(self)
        self.timer_output_tabs.timeout.connect(self.refresh_output_tabs)
        self.timer_output_tabs.start(2000)
        splitter.addWidget(self.output_tabs)
        splitter.setStretchFactor(1, 2147483647)

        self.layout = QVBoxLayout()
        self.layout.addLayout(top_layout)

        self.output_panes['out'].textChanged.connect(self.rebuild_vod_selector)
        # self.minimum_window_size = self.window().size()

        if self.input_pane.toPlainText().strip('\n ') == '':
            self.input_pane.setPlainText(
                'geometry={0}.xyz\nbasis=cc-pV(T+d)Z-PP\ndf-rhf'.format(
                    os.path.basename(self.project.name).replace(' ', '-')))
            import_structure = ''
            if QMessageBox.question(self, '',
                                    'Would you like to import the molecular geometry from a file?',
                                    defaultButton=QMessageBox.Yes) == QMessageBox.Yes:
                import_structure = self.import_structure()
            if not import_structure:
                import_structure = self.database_import_structure()

        self.input_tabs.setCurrentIndex(1 if self.guided_possible() else 0)
        self.initialised_from_input = True
        self.guided_action.setChecked(self.input_tabs.currentIndex() == 1)

        container = QWidget(self)
        container.setLayout(self.layout)
        self.setCentralWidget(container)
        splitter.setSizes([1, 1])

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
        menubar.addAction('New', 'Projects', slot=self.new_action, shortcut='Ctrl+N',
                          tooltip='Create a new project')
        menubar.addAction('Close', 'Projects', self.close, 'Ctrl+W')
        menubar.addAction('Open', 'Projects', self.chooser_open, 'Ctrl+O', 'Open another project')
        menubar.addSeparator('Projects')
        self.recent_menu = RecentMenu(self.window_manager)
        menubar.addSubmenu(self.recent_menu, 'Projects')
        menubar.addSeparator('Projects')
        menubar.addAction('Move to...', 'Projects', self.move_to, tooltip='Move the project')
        menubar.addAction('Copy to...', 'Projects', self.copy_to, tooltip='Make a copy of the project')
        menubar.addAction('Erase', 'Projects', self.erase, tooltip='Completely erase the project')
        menubar.addSeparator('Projects')
        menubar.addAction('Quit', 'Projects', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                          tooltip='Quit')
        menubar.addAction('Import input', 'Files', self.import_input, 'Ctrl+Shift+I',
                          tooltip='Import a file and assign it as the input for the project')
        menubar.addAction('Import structure', 'Files', self.import_structure, 'Ctrl+Alt+I',
                          tooltip='Import an xyz file and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Search external databases for structure', 'Files', self.database_import_structure,
                          'Ctrl+Shift+Alt+I',
                          tooltip='Search PubChem and ChemSpider for a molecule and use it as the source of molecular structure in the input for the project')
        menubar.addAction('Adopt optimised structure from the most recent run', 'Files',
                          lambda dum, self=self: self.database_import_optimised(run=0, file='Optimised.xyz'),
                          tooltip='Adopt structure from the most recent geometry optimisation')
        menubar.addAction('Select a structure from a previous geometry optimisation...', 'Files',
                          self.database_import_optimised,
                          tooltip='Select a structure from a previous geometry optimisation')
        menubar.addAction('Import file', 'Files', self.import_file, 'Ctrl+I',
                          tooltip='Import one or more files, eg geometry definition, into the project')
        menubar.addAction('Export file', 'Files', self.export_file, 'Ctrl+E',
                          tooltip='Export one or more files from the project')
        menubar.addAction('Clean', 'Files', self.clean, tooltip='Remove old runs from the project')
        menubar.addAction('Settings', 'Edit', lambda arg, parent=self: settings_edit(parent), tooltip='Edit settings')
        menubar.addSeparator('Edit')
        menubar.addAction('Structure', 'Edit', self.edit_input_structure, 'Ctrl+D', 'Edit molecular geometry')
        menubar.addAction('Cut', 'Edit', self.input_pane.cut, 'Ctrl+X', 'Cut')
        menubar.addAction('Copy', 'Edit', lambda: QApplication.focusWidget().copy(), 'Ctrl+C', 'Copy')
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
        menubar.addAction('Initial structure', 'View', self.visualise_input,
                          tooltip='View the molecular structure in the job input')
        menubar.addAction('Final structure', 'View', self.visualise_output, 'Alt+D',
                          tooltip='View the molecular structure at the end of the job')
        if self.external_viewer_commands:
            self.external_menu = QMenu('View molecule in external program...')
            for command in self.external_viewer_commands.keys():
                action = self.external_menu.addAction(command)
                action.triggered.connect(lambda dum, command=command: self.visualise_input(
                    external_path=self.external_viewer_commands[command]))

            menubar.addSubmenu(self.external_menu, 'View')
        menubar.addSeparator('View')
        menubar.addAction('Next output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() + 1) % len(self.output_tabs)), 'Alt+]')
        menubar.addAction('Previous output tab', 'View', lambda: self.output_tabs.setCurrentIndex(
            (self.output_tabs.currentIndex() - 1) % len(self.output_tabs)), 'Alt+[')
        self.old_output_menu = OldOutputMenu(self)
        menubar.addSubmenu(self.old_output_menu, 'View')
        menubar.addSeparator('View')
        menubar.addAction('Job stdout', 'View', lambda: self.add_output_tab(0, 'stdout', name='stdout'))
        menubar.addAction('Job stderr', 'View', lambda: self.add_output_tab(0, 'stderr', name='stderr'))

        self.run_action = menubar.addAction('Run', 'Job', self.run, 'Ctrl+R', 'Run Molpro on the project input')
        self.run_force_action = menubar.addAction('Run (force)', 'Job', self.run_force, 'Ctrl+Shift+R',
                                                  'Run Molpro on the project input, even if the input has not changed since the last run')
        self.kill_action = menubar.addAction('Kill', 'Job', self.kill, tooltip='Kill the running job')
        menubar.addAction('Backend', 'Job', lambda: configure_backend(self), 'Ctrl+B', 'Configure backend')
        menubar.addAction('Edit backend configuration file', 'Job', self.edit_backend_configuration, 'Ctrl+Shift+B',
                          'Edit backend configuration file')
        help_manager = HelpManager(menubar)
        help_manager.register('Overview', 'README')
        help_manager.register('Example', 'doc/example.md')
        help_manager.register('Backends', 'doc/backends.md')
        help_manager.register('Display', 'doc/display.md')
        menubar.show()

    def edit_backend_configuration(self):
        self.backend_configuration_editor = BackendConfigurationEditor(
            str(pathlib.Path.home() / '.sjef/molpro/backends.xml'), self)
        self.backend_configuration_editor.exec()

    def edit_input_structure(self):
        f = self.geometry_files()
        if f:
            filename = self.project.filename('', f[-1][1], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            self.destroy_vod('initial structure')
            self.destroy_vod('builder')
            self.embedded_builder(filename)
            self.refresh_output_tabs()
            for i in range(len(self.output_tabs)):
                if self.output_tabs.tabText(i) == 'builder':
                    self.output_tabs.setCurrentIndex(i)

    def destroy_vod(self, title):
        if title in self.vods:
            del self.vods[title]
        for i in range(len(self.output_tabs)):
            if self.output_tabs.tabText(i) == title:
                self.output_tabs.removeTab(i)

    def refresh_output_tabs(self):
        self.old_output_menu.refresh()
        if len(self.output_tabs) != len(
                [tab_name for tab_name, pane in self.output_panes.items() if
                 os.path.exists(self.project.filename(re.sub(r'.*\.', '', tab_name)))]) + len(self.vods):
            self.output_tabs.clear()
            for suffix, pane in self.output_panes.items():
                if os.path.exists(self.project.filename(suffix)):
                    self.output_tabs.addTab(pane, suffix)
            for title, vod in self.vods.items():
                self.output_tabs.addTab(vod, title)
        if 'stderr' not in self.output_panes.keys() and self.project.status == 'completed' and not (
                os.path.exists(self.project.filename('out')) and self.project.out):
            self.add_output_tab(0, suffix='stderr', name='stderr')
        # print('end refresh output tabs')

    def add_output_tab(self, run: int, suffix='out', name=None):
        tab_name = os.path.basename(self.project.filename(suffix, run=run)) if name is None else name
        self.output_panes[tab_name] = ViewProjectOutput(self.project, suffix, instance=run)
        self.output_tabs.addTab(self.output_panes[tab_name], tab_name)
        for i in range(len(self.output_tabs)):
            if self.output_tabs.tabText(i) == tab_name:
                self.output_tabs.setCurrentIndex(i)

    def guided_toggle(self):
        if self.trace: print('guided_toggle')
        index = 1 if self.guided_action.isChecked() else 0
        if 'inp' in self.output_panes:
            if index == 0:
                self.output_panes['inp'].hide()
                for suffix in ['structure', 'out']:
                    for i in range(len(self.output_tabs)):
                        if self.output_tabs.tabText(i) == suffix:
                            self.output_tabs.setCurrentIndex(i)
            else:
                self.output_panes['inp'].show()
                for i in range(len(self.output_tabs)):
                    if self.output_tabs.tabText(i) == 'inp':
                        self.output_tabs.setCurrentIndex(i)
        guided = self.guided_possible()
        if not guided and index == 1:
            box = QMessageBox()
            box.setText('Guided mode cannot be used because the input is too complex')
            spec_input = molpro_input.canonicalise(self.input_specification.input())
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
        if guided:
            self.input_specification = InputSpecification(self.input_pane.toPlainText(),
                                                          directory=self.project.filename())
        self.input_tabs.setTabVisible(self.input_tabs.indexOf(self.guided_pane), guided)

    def guided_possible(self):
        input_text = self.input_pane.toPlainText()
        if not input_text: input_text = ''
        input_specification = InputSpecification(input_text, directory=self.project.filename())
        guided = len(input_specification) and molpro_input.equivalent(input_text, input_specification)
        return guided

    def input_tab_changed_consequence(self, index=0):
        if self.trace: print('input_tab_changed_consequence, index=', index, self.input_tabs.currentIndex())
        if self.input_tabs.currentIndex() == 1:
            self.guided_pane.refresh()

    def available_functionals(self):
        project_registry = self.project.registry('dfunc')
        result = []
        if project_registry != None:
            for priority in range(5, -1, -1):
                for keyfound in project_registry:
                    if project_registry[keyfound]['priority'] == priority:
                        result.append(keyfound)
        return result

    def allowed_methods(self):
        result = []
        if not hasattr(self, 'procedures_registry'):
            try:
                self.procedures_registry = self.project.procedures_registry()
                if not self.procedures_registry:
                    raise ValueError
            except Exception as e:
                msg = QMessageBox()
                msg.setText('Error in finding local molpro')
                msg.setDetailedText('Guided mode will not work correctly\r\n' + str(e))
                msg.exec()
                self.procedures_registry = {}
        for keyfound in self.procedures_registry.keys():
            if self.procedures_registry[keyfound]['class'] == 'PROG':
                result.append(self.procedures_registry[keyfound]['name'])
        return result

    def vod_selector_action(self, text, external_path=None, force=False):
        # print('vod_selector_action', text, external_path, force)
        if force and self.vod_selector.currentText().strip() == 'None':
            self.vod_selector.setCurrentText('Final structure')
        # text = self.vod_selector.currentText().strip()
        # text = ''
        # print('text', text)
        # if text == '': text = text1
        if text == '':
            return
        elif text == 'None':
            pass
        elif text[:5] == 'Edit ':
            filename = self.project.filename('', text[5:], run=-1)
            if not os.path.isfile(filename) or os.path.getsize(filename) <= 1:
                with open(filename, 'w') as f:
                    f.write('1\n\nC 0.0 0.0 0.0\n')
            if external_path:
                subprocess.Popen([external_path, filename])
            else:
                # self.embedded_builder(filename)
                pass
        elif text == 'Initial structure':
            self.visualise_input(external_path=external_path)
        elif text == 'Final structure':
            self.visualise_output(external_path, 'xml')
        else:
            for typ in molpro_input.orbital_types:
                if text.replace(' orbitals', '') == molpro_input.orbital_types[typ]['text']:
                    self.visualise_output(external_path, '', self.project.filename('molden', typ, run=0))

    def rebuild_vod_selector(self):
        for t, f in self.geometry_files():
            self.vod_selector_action('Edit ' + f)
        self.vod_selector_action('Initial structure')
        if self.project.status == 'completed' or (
                os.path.isfile(self.project.filename('xml')) and open(self.project.filename('xml'),
                                                                      'r').read().rstrip()[
                                                                 -9:] == '</molpro>'):
            self.vod_selector_action('Final structure')
            for t, f in self.putfiles():
                if f.replace('.molden', '') in molpro_input.orbital_types:
                    self.vod_selector_action(
                        molpro_input.orbital_types[f.replace('.molden', '')]['text'] + ' orbitals')

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

    def run(self, force=False):
        if self.guided_possible() and ('geometry' not in self.input_specification or (
                self.input_specification['geometry'][-4:] == '.xyz' and not os.path.exists(
            self.project.filename('', self.input_specification['geometry'], run=
            -1)))):
            QMessageBox.critical(self, 'Geometry missing', 'Cannot submit job because no geometry is defined')
            return False
        if 'stderr' in self.output_panes:
            self.output_tabs.removeTab(self.output_tabs.indexOf(self.output_panes['stderr']))
            del self.output_panes['stderr']
            self.refresh_output_tabs()
        try:
            self.project.run(force=force)
        except Exception as e:
            QMessageBox.critical(self, 'Job submission failed', 'Cannot submit job:\n' + str(e))
            return False
        for vod in list(self.vods.keys()):
            if vod not in ['builder', 'initial structure', 'inp']:
                del self.vods[vod]
        for i in range(len(self.output_tabs)):
            if self.output_tabs.tabText(i) == 'out':
                self.output_tabs.setCurrentIndex(i)

    def run_force(self):
        self.run(force=True)

    def kill(self):
        self.project.kill()

    def clean(self):
        self.project.clean()

    def visualise_output(self, external_path=None, typ='xml', name=None):
        filename = self.project.filename(typ, name) if name else self.project.filename(typ)
        if not os.path.exists(filename): return
        if external_path:
            subprocess.Popen([external_path, filename])
        else:
            title = os.path.splitext(os.path.basename(filename))[0]
            if title in molpro_input.orbital_types.keys():
                title = molpro_input.orbital_types[title]['text']
            elif title == os.path.splitext(os.path.basename(self.project.filename()))[0]:
                title = 'final structure'
            if title not in self.vods:
                self.embedded_vod(filename, command='mo HOMO', title=title)

    def embedded_vod(self, file, command='', title='structure', **kwargs):
        width = self.output_tabs.geometry().width() - 310
        height = self.output_tabs.geometry().height() - 40
        firstmodel = 1
        firstvib = 1
        firstorb = 1
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
        if not 'mo_translucent' in settings: settings['mo_translucent'] = 0.3
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
            firstmodel) + """; """ + command + """; mo nomesh fill translucent """ + str(settings['mo_translucent']) + """; mo resolution 7; mo titleFormat ' '",
  use: "HTML5",
  j2sPath: "j2s",
  serverURL: "php/jsmol.php",
};

Jmol.getApplet("myJmol", Info);
</script>
</td>
<td>
<p>
<script>
Jmol.jmolLink(myJmol,'menu','Jmol menu')
</script>
</p>
<table><tr>
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
            for i in range(len(orbs.index)):
                html += ('["model ' + str(firstorb) + '; vibration off; mo ' + str(orbs.index[i]) + '", "' +
                         orbs.orbitals[i]['ID'] +
                         (' occ=' + '{:.3f}'.format(orbs.orbitals[i]['occupation']) if 'occupation' in orbs.orbitals[
                             i] else '') +
                         (' ene=' + '{:.3f}'.format(orbs.orbitals[i]['energy']) if 'energy' in orbs.orbitals[
                             i] else '') +
                         '"],')
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
Jmol.jmolBr()
Jmol.jmolCheckbox(myJmol,'mo TITLEFORMAT "Model %M, MO %I/%N|Energy = %E %U|?Label = %S|?Occupancy = %O"', "mo TITLEFORMAT ' '","orbital info")

Jmol.jmolBr()
</script>
</td>
             """
        elif vibs and vibs.frequencies:
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

        html += """
        </tr>
<script>
Jmol.jmolHtml("<p>")
Jmol.jmolCommandInput(myJmol,'&rarr; Jmol',25,1,'title')
Jmol.jmolHtml("</p>")
</script>
</td>
</tr>
</table>
</body>
</html>"""
        self.add_vod(html, title=title, **kwargs)

    def embedded_builder(self, file, title='builder', **kwargs):
        width = max(400, self.output_tabs.geometry().width() - 310)
        height = max(400, self.output_tabs.geometry().height() - 40)

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
<p>
Click in the top left corner of the display pane for options.<br/>
</p>
<p>
<script>
Jmol.jmolButton(myJmol, 'write """
        filetype = os.path.splitext(file)[1][1:]
        html += filetype + ' "' + file
        html += """\"','Save structure')
Jmol.jmolHtml("</p>")
Jmol.jmolHtml("<p>")
Jmol.jmolLink(myJmol,'menu','Jmol menu')
Jmol.jmolHtml("</p>")
Jmol.jmolHtml("<p>")
Jmol.jmolCommandInput(myJmol,'&rarr; Jmol',25,1,'title')
Jmol.jmolHtml("</p>")
</script>
</td>
</tr>
</table>
</body>
</html>"""

        self.add_vod(html, title=title, **kwargs)

    def add_vod(self, *args, title='structure', **kwargs):
        # print('add_vod', title)
        if title in self.vods.keys():
            # print('duplicate vod',title)
            return
        vod = VOD(*args, directory=self.project.filename(run=-1), title=title, **kwargs)
        vod.hide()
        self.vods[vod.title] = vod

    def visualise_input(self, external_path=None):
        import tempfile
        geometry_directory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometry_directory.mkdir(exist_ok=True)
        xyz_file = str(geometry_directory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        if not os.path.isfile(xyz_file) or os.path.getmtime(xyz_file) < os.path.getmtime(
                self.project.filename('inp', run=-1)) or any(
            [os.path.getmtime(xyz_file) < os.path.getmtime(self.project.filename('', gfile[1], run=-1)) for gfile in
             self.geometry_files()]):
            with tempfile.TemporaryDirectory() as tmpdirname:
                path = pathlib.Path(tmpdirname) / 'input_geometries'
                os.makedirs(str(path), exist_ok=True)
                self.project.copy(pathlib.Path(self.project.filename(run=-1)).name, location=path)
                project_path = path / pathlib.Path(self.project.filename(run=-1)).name
                project = Project(str(project_path))
                project.clean(0)
                open(project.filename('inp', run=-1), 'a').write('\nhf\n---')
                with open(pathlib.Path(project.filename(run=-1)) / 'molpro.rc', 'a') as f:
                    f.write(' --geometry')

                project.run(wait=True, force=True, backend='local')
                if not project.xpath_search('//*/cml:atomArray'):
                    detail = ''
                    for suffix in ['stdout', 'stderr', 'out']:
                        try:
                            with open(project.filename(suffix, run=0), 'r') as ff:
                                detail += ''.join(ff.readlines())
                        except:
                            pass
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setWindowTitle("Error")
                    msg.setText('Error in calculating input geometry')
                    msg.setDetailedText(detail)
                    msg.exec_()
                    return
                geometry = project.geometry()
                current_dir = os.path.dirname(self.project.filename(run=-1))
                trash_project(project)
                settings['project_directory'] = current_dir
                with open(xyz_file, 'w') as f:
                    f.write(str(len(geometry)) + '\n\n')
                    for atom in geometry:
                        f.write(atom['elementType'])
                        for c in atom['xyz']: f.write(' ' + str(c * .529177210903))
                        f.write('\n')
        if external_path:
            subprocess.Popen([external_path, xyz_file])
        elif 'builder' not in self.vods and 'initial structure' not in self.vods:
            self.embedded_vod(xyz_file, command='', title='initial structure')

    def closeEvent(self, a0, QCloseEvent=None):
        self.close_signal.emit(self)

    def new_action(self):
        self.new_signal.emit(self)

    def chooser_open(self):
        self.chooser_signal.emit(self)

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
                                                     "Geometry (*.xyz)",
                                                     options=QFileDialog.DontResolveSymlinks)
        if os.path.isfile(filename):
            settings['geometry_directory'] = os.path.dirname(filename)
            self.adopt_structure_file(filename)
            self.edit_input_structure()
            return filename

    def adopt_structure_file(self, filename):
        if os.path.exists(filename):
            self.project.import_file(filename)
            text = self.input_pane.toPlainText()
            if re.search(r'geometry *= *[-_./\w]+ *[;\n]', text, flags=re.IGNORECASE):
                self.input_pane.setPlainText(
                    re.sub('geometry *=.*[\n;]', 'geometry=' + os.path.basename(filename) + '\n', text))
                self.rebuild_vod_selector()
            else:
                self.input_pane.setPlainText('geometry=' + os.path.basename(filename) + '\n' + text)

    def database_import_structure(self):
        if filename := database_choose_structure():
            self.adopt_structure_file(filename)
            os.remove(filename)
            os.rmdir(os.path.dirname(filename))
            self.edit_input_structure()
            return filename

    def database_import_optimised(self, run=None, file=None):
        run_directories = self.run_directories
        for k in range(len(run_directories)):
            run_directories[k] = os.path.splitext(os.path.basename(run_directories[k]))[0]
        if len(run_directories) <= 1: return None
        run_ = 1 if len(run_directories) == 2 else run if run else None
        if run_ is None:
            selected_, ok = QInputDialog.getItem(self, 'Choose run from which to obtain optimised geometry',
                                                 'Which run?',
                                                 run_directories[-1:0:-1])
            return self.database_import_optimised(run_directories[1:].index(selected_) + 1, file) if ok else None
        else:
            filename = ''
            if file:
                filename = file
            else:
                files_ = self.optimised_structure_files(run_)
                k, ok = QInputDialog.getItem(self, 'Choose geometry',
                                             'Which geometry from run ' + run_directories[
                                                 run_] + ' should be selected?', files_.keys())
                if ok:
                    filename = files_[k]
            if filename:
                self.adopt_structure_file(pathlib.Path(self.run_directories[run_]) / filename)
                self.edit_input_structure()
                return filename

    def optimised_structure_files(self, run=0):
        run_directory_ = self.project.filename('', '', run)
        files = glob.glob('[Oo]ptimised*.xyz', root_dir=run_directory_)
        files_ = {}
        if 'Optimised.xyz' in files: files_['final'] = 'Optimised.xyz'
        files.sort(reverse=True)
        for fn in files:
            if 'optimised_' in fn:
                files_[re.sub('optimised_', '', re.sub('.xyz', '', fn))] = fn
        return files_

    @property
    def run_directories(self):
        last_filename = self.project.filename('', '', 0)
        result = [last_filename]
        if last_filename == self.project.filename('', '', -1):
            return []
        for i in range(1, 100000):
            filename = self.project.filename('', '', i)
            result.append(filename)
            if filename == last_filename: break
        return result

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
        file_name, filter_ = QFileDialog.getSaveFileName(self, 'Move project to...',
                                                         os.path.dirname(self.project.filename(run=-1)),
                                                         'Molpro project (*.molpro)', )
        if file_name:
            self.project.move(file_name)
            self.window_manager.register(ProjectWindow(file_name, self.window_manager))
            self.close()

    def copy_to(self):
        file_name, filter_ = QFileDialog.getSaveFileName(self, 'Copy project to...',
                                                         os.path.dirname(self.project.filename(run=-1)),
                                                         'Molpro project (*.molpro)', )
        if file_name:
            self.project.copy(file_name, keep_run_directories=0)
            return file_name

    def erase(self):
        result = QMessageBox.question(self, 'Erase project',
                                      'Are you sure you want to erase project ' + self.project.filename(run=-1))
        if result == QMessageBox.Yes:
            current_dir = os.path.dirname(self.project.filename(run=-1))
            trash_project(self.project)
            settings['project_directory'] = current_dir
            self.close()

    def show_input_specification(self):
        QMessageBox.information(self, 'Input specification', 'Input specification:\r\n' +
                                re.sub('}$', '\n}', re.sub('^{', '{\n  ', str(self.input_specification))).replace(', ',
                                                                                                                  ',\n  '))


def trash_project(project):
    trash = pathlib.Path(settings['Trash'])
    trash.mkdir(parents=True, exist_ok=True)
    project.move(str(trash / os.path.basename(project.filename(run=-1))))


class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if level > 0 and 'Synchronous XMLHttpRequest' not in message:
            print('javaScriptConsoleMessage', level, message, lineNumber, sourceID, file=sys.stderr)


class VOD(QWebEngineView):
    def __init__(self, html, directory=None, width=800, height=420, verbosity=0, title='structure'):
        if verbosity:
            print(html)
            open('test.html', 'w').write(html)
        super().__init__()
        self.directory_ = directory
        self.title = title
        self.page_ = WebEnginePage()
        self.setPage(self.page_)
        if self.directory_ is not None:
            self.page().profile().downloadRequested.connect(self._download_requested)
        self.setHtml(html, QUrl.fromLocalFile(str(pathlib.Path(__file__).resolve())))

        self.setMinimumSize(width, height)

    def _download_requested(self, item):
        import re
        if item.downloadFileName():
            item.setDownloadFileName(re.sub(r' \(\d+\)\.', r'.', item.downloadFileName()))
            item.setDownloadDirectory(self.directory_)
            item.accept()


class BasisAndHamiltonianChooser(QWidget):
    r"""
    Choose basis and hamiltonian
    """
    null_prompt = '- Select -'
    all_qualities = 'All Qualities'
    basis_qualities = [all_qualities, 'SZ', 'DZ', 'TZ', 'QZ', '5Z', '6Z']

    def __init__(self, parent: ProjectWindow):
        super().__init__(parent)
        self.parent = parent

        self.basis_registry = self.parent.project.basis_registry()
        self.desired_basis_quality = self.parent.input_specification.basis_quality

        self.combo_hamiltonian = QComboBox(self)
        self.combo_hamiltonian.addItems([h['text'] for h in molpro_input.hamiltonians.values()])
        self.combo_hamiltonian.currentTextChanged.connect(self.changed_hamiltonian)

        self.guided_combo_basis_quality = QComboBox(self)
        self.guided_combo_basis_quality.addItems(self.basis_qualities)
        self.guided_combo_basis_quality.currentTextChanged.connect(self.changed_basis_quality)

        self.guided_combo_basis_default = QComboBox(self)
        self.guided_combo_basis_default.currentTextChanged.connect(self.changed_default_basis)

        # layout = QFormLayout(self)
        # layout.addRow('Hamiltonian', self.combo_hamiltonian)
        # layout.addRow('Basis set quality', self.guided_combo_basis_quality)
        # layout.addRow('Default Basis Set', self.guided_combo_basis_default)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(RowOfTitledWidgets({
            'Hamiltonian': self.combo_hamiltonian,
            'Quality': self.guided_combo_basis_quality,
            'Basis': self.guided_combo_basis_default,
        }, title='Hamiltonian and basis'))

    def refresh(self):
        while True:
            if not 'basis' in self.input_specification or not 'default' in self.input_specification['basis'] or not \
                    self.input_specification['basis']['default']:
                self.input_specification['basis'] = self.default_basis_for_hamiltonian(
                    self.desired_basis_quality if self.desired_basis_quality > 0 else 3)
                continue

            possible_basis_sets = [k for k in self.basis_registry.keys() if (  # True or
                    self.desired_basis_quality == 0 or self.basis_registry[k][
                'quality'] == self.basis_qualities[self.desired_basis_quality]
            )
                                   and (
                                           not 'hamiltonian' in self.input_specification or
                                           self.hamiltonian_type(k) == self.input_specification[
                                               'hamiltonian']
                                   )]
            self.guided_combo_basis_default.clear()
            self.guided_combo_basis_default.addItems([self.null_prompt] + possible_basis_sets)
            if self.input_specification['basis']['elements'] or not self.input_specification['basis'][
                                                                        'default'] in possible_basis_sets:
                self.guided_combo_basis_default.setCurrentText(self.null_prompt)
            else:
                self.guided_combo_basis_default.setCurrentText(self.input_specification['basis']['default'])
            self.guided_combo_basis_default.show()

            self.guided_combo_basis_quality.setCurrentText(self.basis_qualities[self.desired_basis_quality])
            self.combo_hamiltonian.setCurrentText(
                molpro_input.hamiltonians[self.input_specification['hamiltonian']]['text'])
            break

    def changed_hamiltonian(self, text):
        new_hamiltonian_ = list(molpro_input.hamiltonians.keys())[
            [v['text'] for v in molpro_input.hamiltonians.values()].index(text)]
        if self.input_specification['hamiltonian'] != new_hamiltonian_:
            self.input_specification['hamiltonian'] = new_hamiltonian_
            if 'basis' in self.input_specification and 'default' in self.input_specification['basis']:
                self.input_specification['basis'] = self.default_basis_for_hamiltonian(self.desired_basis_quality)
            self.write()
            self.refresh()

    def changed_basis_quality(self, text):
        if self.desired_basis_quality != self.basis_qualities.index(text):
            self.desired_basis_quality = self.basis_qualities.index(text)
            self.refresh()

    def default_basis_for_hamiltonian(self, desired_basis_quality=0):
        quality = self.desired_basis_quality if desired_basis_quality > 0 else 3
        return {'default': 'cc-pV(' + self.basis_qualities[quality][0] + '+d)Z' +
                           molpro_input.hamiltonians[self.input_specification['hamiltonian']]['basis_string'],
                'elements': {}, 'quality': quality}

    def changed_default_basis(self, text):
        if not text or text == self.null_prompt or text == self.input_specification['basis']['default']: return
        self.input_specification['basis']['default'] = text
        self.input_specification['basis']['elements'] = {}
        self.input_specification['basis']['quality'] = self.input_specification.basis_quality
        self.write()

    def write(self):
        self.parent.refresh_input_from_specification()

    @property
    def input_specification(self):
        return self.parent.input_specification

    @property
    def hamiltonians(self):
        result = set()
        for keyfound in self.basis_registry.keys():
            if keyfound is not None:
                result.add(self.hamiltonian_type(keyfound))
        return result

    def hamiltonian_type(self, key):
        return re.sub(r'\(.*', '', self.basis_registry[key]['type'])


class GuidedPane(QWidget):
    method_changed_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.project = self.parent.project
        self.trace = self.parent.trace
        self.input_pane = self.parent.input_pane
        self.setContentsMargins(0, 0, 0, 0)
        self.method_asserted = False

        self.guided_layout = QVBoxLayout()
        self.guided_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.guided_layout)

        self.guided_combo_orientation = QComboBox(self)
        self.guided_combo_orientation.addItems(molpro_input.orientation_options.keys())
        self.guided_combo_orientation.currentTextChanged.connect(
            lambda text: self.input_specification_change('orientation', text))

        self.charge_line = ChargeSelector()
        self.charge_line.textChanged.connect(lambda text: self.input_specification_variable_change('charge', text))

        self.spin_line = SpinComboBox(self, 0, 14)
        self.spin_line.spin_changed.connect(
            lambda ms2: self.input_specification_variable_change('spin', str(ms2) if ms2 >= 0 else ''))

        self.guided_combo_wave_fct_symm = QComboBox(self)
        self.guided_combo_wave_fct_symm.addItems(molpro_input.wave_fct_symm_commands.keys())
        self.guided_combo_wave_fct_symm.currentTextChanged.connect(
            lambda text: self.input_specification_change('wave_fct_symm', text))

        self.guided_combo_job_type = QComboBox(self)
        self.guided_combo_job_type.setMaximumWidth(180)
        self.guided_combo_job_type.addItems(molpro_input.job_type_steps.keys())
        self.guided_combo_job_type.currentTextChanged.connect(
            lambda text: self.input_specification_change('job_type', text))

        self.guided_combo_method = QComboBox(self)

        self.guided_combo_method.addItems(self.parent.allowed_methods())
        self.guided_combo_method.currentTextChanged.connect(
            lambda text: self.input_specification_change('method', text))

        self.guided_combo_functional = QComboBox(self)
        self.guided_combo_functional.addItems(self.parent.available_functionals())
        self.guided_combo_functional.hide()
        self.guided_combo_functional.currentTextChanged.connect(
            lambda text: self.input_specification_change('density_functional', text))

        self.guided_combo_core_correlation = QComboBox(self)
        self.guided_combo_core_correlation.addItems(['large', 'mixed', 'small'])
        self.guided_combo_core_correlation.hide()
        self.guided_combo_core_correlation.currentTextChanged.connect(
            lambda text: self.input_specification_change('core_correlation', text))

        self.checkbox_df = QCheckBox()
        self.checkbox_df.clicked.connect(lambda text: self.input_specification_change('density_fitting', text))

        self.combo_properties = PropertyInput(self)

        self.method_row = RowOfTitledWidgets({'Type': self.guided_combo_job_type, 'Method': self.guided_combo_method,
                                              'Functional': self.guided_combo_functional, }, title='Calculation')
        self.guided_layout.addWidget(self.method_row)

        self.desired_basis_quality = 0
        self.basis_and_hamiltonian_chooser = BasisAndHamiltonianChooser(self)
        self.guided_layout.addWidget(self.basis_and_hamiltonian_chooser)

        self.thresholds_button = QPushButton('Thresholds')
        self.thresholds_button.clicked.connect(self.thresholds_edit)
        self.thresholds_button.setToolTip('Specify global thresholds')
        self.thresholds_button.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')

        self.print_button = QPushButton('Print')
        self.print_button.clicked.connect(self.print_edit)
        self.print_button.setToolTip('Specify global print levels')
        self.print_button.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')

        self.method_options_button = QPushButton('Options')  # TODO delete when we are settled
        self.method_options_button.clicked.connect(self.method_options_edit)
        self.method_options_button.setToolTip('Specify options for the main method')

        self.step_options_combo = QComboBox(self)
        self.step_options_combo.currentIndexChanged.connect(
            lambda text: self.step_options_edit(int(text - 1)))

        self.guided_layout.addWidget(RowOfTitledWidgets({
            'Charge': self.charge_line,
            'Spin': self.spin_line,
            'Symmetry': self.guided_combo_wave_fct_symm,
        }, title='Wavefunction parameters'))

        self.guided_orbitals_input = OrbitalInput(self)
        self.guided_layout.addWidget(RowOfTitledWidgets({
            'Express orbitals': self.guided_orbitals_input,
            'Expectation values': self.combo_properties,
        }, title='Properties'))
        misc_layout = QHBoxLayout()
        self.guided_layout.addLayout(misc_layout)
        misc_layout.addWidget(RowOfTitledWidgets({
            'Orientation': self.guided_combo_orientation,
            'Density Fitting': self.checkbox_df,
            'Options': self.step_options_combo,
        }, title='Miscellaneous'))
        options_layout = QGridLayout()
        options_layout.addWidget(self.thresholds_button, 0, 0)
        options_layout.addWidget(self.print_button, 1, 0)
        # options_layout.addWidget(self.method_options_button,0,0)
        misc_layout.addLayout(options_layout)
        self.guided_layout.addStretch()

    @property
    def input_specification(self):
        return self.parent.input_specification

    def refresh(self):
        self.guided_combo_orientation.setCurrentText(
            self.input_specification['orientation'] if 'orientation' in self.input_specification else
            list(molpro_input.orientation_options.keys())[0])
        self.guided_combo_wave_fct_symm.setCurrentText(
            self.input_specification['wave_fct_symm'] if 'wave_fct_symm' in self.input_specification else
            list(molpro_input.wave_fct_symm_commands.keys())[0])
        if 'variables' in self.input_specification and 'charge' in self.input_specification['variables']:
            self.charge_line.setText(self.input_specification['variables']['charge'])
        else:
            self.charge_line.setText('0')

        self.spin_line.refresh(self.input_specification.spin)

        if self.input_specification is not None:
            if self.input_specification.method is None:
                self.input_specification.method = 'rhf'
            base_method = re.sub('^df-', '', self.input_specification.method, flags=re.IGNORECASE)
            method_index = self.guided_combo_method.findText(base_method, Qt.MatchFixedString)
            self.guided_combo_method.setCurrentIndex(method_index)
            if re.match('[ru]ks', self.input_specification.method, flags=re.IGNORECASE):
                self.method_row.ensure_not(['Core Correlation'])
                self.method_row.ensure({'Functional': self.guided_combo_functional, })
                if not self.input_specification.density_functional:
                    self.input_specification.density_functional = self.guided_combo_functional.itemText(0)
                self.guided_combo_functional.setCurrentIndex(self.guided_combo_functional.findText(
                    self.input_specification.density_functional, Qt.MatchFixedString))
            elif re.match('[ru]hf', self.input_specification.method):
                self.method_row.ensure_not(['Functional'])
                self.method_row.ensure_not(['Core Correlation'])
            else:
                self.method_row.ensure_not(['Functional'])
                self.method_row.ensure({'Core Correlation': self.guided_combo_core_correlation, })
        self.guided_combo_job_type.setCurrentText(self.input_specification.job_type)
        if 'core_correlation' in self.input_specification:
            self.guided_combo_core_correlation.setCurrentText(self.input_specification['core_correlation'])

        self.step_options_combo.clear()
        self.step_options_combo.addItem('')
        self.step_options_combo.addItems([step['command'].upper() for step in self.input_specification['steps']])
        self.step_options_combo.setCurrentIndex(0)
        try:
            registry_df = self.parent.procedures_registry[self.input_specification.method.upper()][
                'DF']  # TODO do something about negative sign in registry
            bit_pattern = '0000' + bin(abs(registry_df)).replace('b', '0') if registry_df is not None else '0000'
            # print(registry_df, bin(registry_df),bit_pattern)
            closed_shell = bit_pattern[-1] == '1'
            open_shell = bit_pattern[-2] == '1'
            available = open_shell if self.input_specification.open_shell_electrons > 0 else closed_shell
            mandatory = bit_pattern[-4] == '1'
            if not available:
                # print('density fitting not possible')
                self.checkbox_df.setDisabled(True)
                self.checkbox_df.setChecked(False)
                self.input_specification['density_fitting'] = False
            elif mandatory:
                # print('density fitting mandatory',bit_pattern[-4],bit_pattern[-2],bit_pattern[-1])
                self.checkbox_df.setDisabled(True)
                self.checkbox_df.setChecked(True)
                self.input_specification['density_fitting'] = True
            else:
                # print('density fitting possible')
                self.checkbox_df.setDisabled(False)
                if self.method_asserted:
                    # print('asserted')
                    self.input_specification['density_fitting'] = int(registry_df) > 0
                    self.method_asserted = False
                # print('df option','density_fitting' in self.input_specification and self.input_specification['density_fitting'])
                self.checkbox_df.setChecked(
                    'density_fitting' in self.input_specification and self.input_specification['density_fitting'])
            self.refresh_input_from_specification()
        except KeyError:
            self.checkbox_df.setDisabled(True)

        self.basis_and_hamiltonian_chooser.refresh()

        self.guided_orbitals_input.refresh()

    # def orbitals_input_action(self, parameter):
    #     if not 'postscripts' in self.input_specification: self.input_specification['postscripts'] = []
    #     self.input_specification['postscripts'] = [ps for ps in self.input_specification['postscripts'] if
    #                                                ps != self.orbital_put_command]
    #     if parameter:
    #         self.input_specification['postscripts'].append(self.orbital_put_command)
    #     self.refresh_input_from_specification()
    #     self.guided_orbitals_input.setChecked(parameter)

    # @property
    # def orbital_put_command(self):
    #     return 'put,molden,' + os.path.basename(os.path.splitext(self.project.filename(run=-1))[0]) + '.molden'

    def input_specification_change(self, key, value):
        if value is None or (
                key in self.input_specification and str(self.input_specification[key]).lower() == str(value).lower()):
            return
        if key == 'method':
            self.input_specification.method = value
            self.method_changed_signal.emit(value)
            if self.parent.initialised_from_input:
                self.method_asserted = True
            self.input_specification.polish()
        elif key == 'job_type':
            self.input_specification.job_type = value
        elif key == 'density_functional':
            self.input_specification.density_functional = value
        else:
            self.input_specification[key] = value
        self.refresh_input_from_specification()
        self.refresh()

    def input_specification_variable_change(self, key, value):
        # print('input_specification_variable_change',key,value)
        value_ = value
        if 'variables' not in self.input_specification:
            self.input_specification['variables'] = {}
        if key == 'charge':
            if value == '-': return
            try:
                old_charge = int(self.input_specification['variables']['charge'])
            except:
                old_charge = 0
            value_ = str(int(value_) if value_.isdigit() else value_ if value_ else '0')
            if int(value_) != old_charge:
                self.input_specification.spin = None
        self.input_specification['variables'][key] = value_
        if key == 'charge':
            self.refresh()
        if key == 'spin':
            if value_:
                self.input_specification.spin = value_
            else:
                self.input_specification.spin = None
        self.refresh_input_from_specification()

    def refresh_input_from_specification(self):
        if self.trace: print('refresh_input_from_specification')
        if not self.parent.guided_possible(): return
        new_input = self.input_specification.input()
        if not molpro_input.equivalent(self.input_pane.toPlainText(), new_input):
            self.input_pane.setPlainText(new_input)

    def thresholds_edit(self, flag):
        project_registry = self.project.registry('THRESH')
        available_options = [k.split(',')[0] for k in project_registry]
        title = 'Global thresholds'
        box = OptionsDialog(
            self.parent.input_specification['thresholds'] if 'thresholds' in self.parent.input_specification else {},
            available_options, title=title, parent=self,
            help_uri='https://www.molpro.net/manual/doku.php?id=program_control&s[]=gthresh#global_thresholds_gthresh')
        result = box.exec()
        if result is not None:
            self.parent.input_specification['thresholds'] = result
            self.refresh_input_from_specification()

    def print_edit(self, flag):
        available_options = [
            'BASIS',
            'DISTANCE',
            'ANGLES',
            'ORBITAL',
            'ORBEN',
            'CIVECTOR',
            'PAIRS',
            'CS',
            'CP',
            'REF',
            'PSPACE',
            'MICRO',
            'CPU',
            'IO',
            'VARIABLE',
        ]
        title = 'Global print levels'
        box = OptionsDialog(
            self.parent.input_specification['prints'] if 'prints' in self.parent.input_specification else {},
            available_options, title=title, parent=self,
            help_uri='https://www.molpro.net/manual/doku.php?id=program_control#global_print_options_gprint_nogprint')
        result = box.exec()
        if result is not None:
            self.parent.input_specification['prints'] = result
            self.refresh_input_from_specification()

    def step_options_edit(self, step: int):
        if step < 0: return
        step_ = self.parent.input_specification['steps'][step]
        method_ = step_['command'].upper()
        available_options = [re.sub('.*:', '', option) for option in
                             list(self.parent.procedures_registry[method_.replace('FREQUENCIES', 'FREQ')]['options'])]
        title = 'Options for step ' + str(step + 1) + ' (' + method_ + ')'
        existing_options = {o.split('=')[0]: o.split('=')[1] if len(o.split('=')) > 1 else '' for o in
                            (step_['options'] if 'options' in step_ else [])}
        box = OptionsDialog(existing_options, available_options, title=title, parent=self,
                            help_uri='https://www.molpro.net/manual/doku.php?q=' + method_ + '&do=search')
        result = box.exec()
        if result is not None:
            self.parent.input_specification['steps'][step]['options'] = [k + '=' + v if v else k for k, v in
                                                                         result.items()]
            self.refresh_input_from_specification()
        self.step_options_combo.setCurrentIndex(0)

    def method_options_edit(self, flag):
        return self.step_options_edit([s['command'] for s in self.parent.input_specification['steps']].index(
            self.parent.input_specification.method))
        # method_ = self.parent.input_specification.method
        # available_options = [re.sub('.*:','',option) for option in list(self.parent.procedures_registry[method_.upper()]['options'])]
        # title = 'Options for method ' + self.parent.input_specification.method
        # existing_options = {o.split('=')[0]:o.split('=')[1] if len(o.split('='))>1 else '' for o in self.parent.input_specification.method_options}
        # box = OptionsDialog(existing_options, available_options, title=title, parent=self, help_uri='https://www.molpro.net/manual/doku.php?q='+method_+'&do=search')
        # result = box.exec()
        # if result is not None:
        #     self.parent.input_specification.method_options = [k+'='+v if v else k for k,v in result.items()]
        #     self.refresh_input_from_specification()


class RowOfTitledWidgets(QWidget):
    def __init__(self, widgets, title=None, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        # self.setStyleSheet('background-color: lightblue;')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if title is not None:
            q_label = QLabel(title + ':')
            q_label.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(q_label)
        subpane = QWidget(self)
        subpane.setContentsMargins(0, 0, 0, 0)
        subpane.setStyleSheet('font-size: ' + str(self.fontInfo().pointSize() - 1) + 'pt;')
        subpane.setAutoFillBackground(True)
        layout.addWidget(subpane)
        self.layout2 = QGridLayout(subpane)
        self.layout2.setContentsMargins(0, 0, 0, 0)
        self.layout2.setSpacing(0)
        self.widgets = {}
        self.widget_captions = {}
        self.ensure(widgets)

    def ensure(self, widgets):
        for k, v in widgets.items():
            if k not in self.widgets.keys():
                self.widget_captions[k] = QLabel(k)
                self.layout2.addWidget(self.widget_captions[k], 0, len(self.widgets), alignment=Qt.AlignCenter)
                self.layout2.addWidget(v, 1, len(self.widgets), alignment=Qt.AlignCenter)
                self.widgets[k] = v
                self.widget_captions[k].show()
                self.widgets[k].show()

    def ensure_not(self, widget_keys):
        for k in widget_keys:
            if k in self.widgets.keys():
                self.layout2.removeWidget(self.widget_captions[k])
                self.layout2.removeWidget(self.widgets[k])
                self.widgets[k].hide()
                self.widget_captions[k].hide()
                del self.widgets[k]
                del self.widget_captions[k]


class OrbitalInput(CheckableComboBox):
    r"""
    Helper for constructing input for producing various kinds of orbitals
    """

    def __init__(self, parent=None, null_text='None'):
        super().__init__(null_text=null_text)
        self.parent = parent
        self.refresh()
        self.model().dataChanged.connect(self.action)

    def refresh(self):
        self.clear()
        self.addItems([o['text'] for k, o in molpro_input.orbital_types.items() if
                       k != 'nbo' or self.parent.input_specification.open_shell_electrons is None or self.parent.input_specification.open_shell_electrons == 0])
        if 'orbitals' in self.parent.input_specification:
            for o in self.parent.input_specification['orbitals']:
                for i in range(self.model().rowCount()):
                    if self.model().item(i).text() == molpro_input.orbital_types[o]['text']:
                        self.model().item(i).setCheckState(Qt.Checked)
        self.updateText()

    def action(self, text):
        self.parent.input_specification['orbitals'] = [k for k, v in molpro_input.orbital_types.items() for t in
                                                       self.currentData() if t == v['text']]
        if any([b in self.parent.input_specification['orbitals'] for b in ['nbo', 'ibo']]):
            self.parent.input_specification_change('wave_fct_symm', 'No Symmetry')
        self.parent.refresh_input_from_specification()


class PropertyInput(CheckableComboBox):
    r"""
    Helper for constructing input for properties
    """

    def __init__(self, parent=None):
        super().__init__(parent, null_text='None')
        self.parent = parent
        self.addItems(molpro_input.properties.keys())
        if 'properties' in self.parent.input_specification:
            for o in self.parent.input_specification['properties']:
                for i in range(self.model().rowCount()):
                    if self.model().item(i).text() == o:
                        self.model().item(i).setCheckState(Qt.Checked)
        self.model().dataChanged.connect(self.refresh)

    def refresh(self, text):
        self.parent.input_specification['properties'] = [k for k, v in molpro_input.properties.items() for t in
                                                         self.currentData() if t == k]
        self.parent.input_specification.polish()
        self.parent.refresh_input_from_specification()


class ChargeSelector(QWidget):
    textChanged = pyqtSignal(str, name='textChanged')

    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.label = QLabel('0')
        self.plus_button = QToolButton()
        self.plus_button.setArrowType(Qt.UpArrow)
        self.minus_button = QToolButton()
        self.minus_button.setArrowType(Qt.DownArrow)
        fontsize = self.fontInfo().pointSize()
        self.minus_button.setIconSize(QSize(fontsize // 2, fontsize * 2 // 3))
        self.plus_button.setIconSize(QSize(fontsize // 2, fontsize * 2 // 3))
        self.layout.addWidget(self.minus_button)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.plus_button)
        self.plus_button.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.minus_button.clicked.connect(lambda: self.change(-1))
        self.plus_button.clicked.connect(lambda: self.change(1))

    def setText(self, value):
        self.label.setText(str(value))

    def text(self):
        return self.label.text()

    def change(self, amount=1):
        self.label.setText(str(int(self.label.text()) + amount))
        self.textChanged.emit(self.label.text())
