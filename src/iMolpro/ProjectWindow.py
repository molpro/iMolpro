import concurrent.futures
import datetime
import difflib
import glob
import os
import pathlib
import threading
import time

from pymolpro.elements import periodic_table

from .project import Project, Structure

try:
    import pwd
except ImportError:
    pass
import shutil
import subprocess
import sys
import re
import platform

import pymolpro

try:
    from PySide6.QtCore import QTimer, Signal as pyqtSignal, Qt, QEvent
    from PySide6.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
        QMessageBox, QFileDialog, QSplitter, QInputDialog, QApplication
    from PySide6.QtGui import QDesktopServices, QAction
    # from PySide6.QtCore.Qt.AlignmentFlag import Qt_AlignCenter, Qt_AlignTop
except ImportError as e:
    # print('PySide6 not found. Trying PyQt6',str(e))
    try:
        from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QEvent
        from PyQt6.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
            QMessageBox, QFileDialog, QSplitter, QInputDialog, QApplication
        from PyQt6.QtGui import QDesktopServices, QAction
        import PyQt6.QtCore
        # from Qt.AlignmentFlag import AlignVCenter as Qt_AlignCenter, AlignTop as Qt_AlignTop
    except ImportError as e:
        # print('PyQt6 not found. Trying PyQt5',str(e))
        from PyQt5.QtCore import QTimer, pyqtSignal, Qt, QEvent
        from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
            QMessageBox, QFileDialog, QSplitter, QInputDialog, QApplication, QAction
        from PyQt5.QtGui import QDesktopServices
        # from PyQt5.QtCore.Qt import AlignCenter as Qt_AlignCenter, AlignTop as Qt_AlignTop

try:
    Orientation = Qt.Orientation
except:
    Orientation = Qt

from pymolpro import molpro_input
from pymolpro.molpro_input import InputSpecification
from .database import database_choose_structure
from .utilities import EditFile, writable_directory
from .backend import configure_backend, BackendConfigurationEditor
from .settings import settings
from .theme import apply_theme
from .vtk_molecule_widget import MoleculeScene

from .status_bar import StatusBar
from .output_tabs import MyTabWidget, OutputTabWidget
from .guided_pane import GuidedPane
from .project_window_menu import setup_project_window_menubar

import logging

logger = logging.getLogger(__name__)


class ProjectWindow(QMainWindow):
    close_signal = pyqtSignal(QWidget, name='closeSignal')
    new_signal = pyqtSignal(QWidget, name='newSignal')
    chooser_signal = pyqtSignal(QWidget, name='chooserSignal')
    # Emitted from the background thread that submits a job (see run()); Qt automatically
    # delivers this via a queued connection onto the GUI thread since self lives there, unlike
    # QTimer.singleShot() which needs an event loop on the *calling* thread to ever fire and so
    # silently never runs when called from a plain background thread.
    run_finished_signal = pyqtSignal(object, name='runFinishedSignal')
    null_prompt = '- Select -'
    all_qualities = 'All Qualities'
    basis_qualities = [all_qualities, 'SZ', 'DZ', 'TZ', 'QZ', '5Z', '6Z']

    def changeEvent(self, event):
        super().changeEvent(event)
        # logger.debug('event.type() ' + str(event.type))
        if True or event.type() == QEvent.WindowStateChange:
            # logger.debug('windowStateChange')
            # logger.debug('full screen ? ' + str(self.isFullScreen()))
            if not self.isFullScreen():
                self.normal_geometry = self.normalGeometry()
            # logger.debug('normal_geometry ' + str(self.normal_geometry))
            settings['project_window_width'] = self.normal_geometry.width()
            settings['project_window_height'] = self.normal_geometry.height()
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            menubar = self.menuBar()
            if menubar is not None and hasattr(self, 'window_manager'):
                self.window_manager.set_cli_action_owner(menubar)

    def __init__(self, filename, window_manager, latency=1000, **kwargs):
        # print('ProjectWindow.__init__ entered')
        logger.debug('Initializing ProjectWindow with filename {}'.format(filename))
        super().__init__(None)
        self.window_manager = window_manager
        self.latency = latency
        if 'project_window_width' not in settings:
            settings['project_window_width'] = 1311
        if 'project_window_height' not in settings:
            settings['project_window_height'] = 576
        if 'project_window_width' in settings and 'project_window_height' in settings:
            width, height = settings['project_window_width'], settings['project_window_height']
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                width = min(width, available.width())
                height = min(height, available.height())
            self.resize(width, height)
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.initialised_from_input = False
        self._initial_xyz_lock = threading.Lock()
        # Held for the duration of a background job submission (see run()), so StatusBar's
        # timer-driven polling doesn't call into the sjef project object concurrently with it.
        self._run_lock = threading.Lock()
        self.run_finished_signal.connect(self._run_submitted)
        # Cache of (input text, parsed geom) from the last _initial_xyz_staleness() call, so a
        # fresh InputSpecification parse is only done when the input pane text has actually
        # changed since the last check, rather than on every ~1s timer tick.
        self._initial_xyz_geom_cache = (None, "")
        # Suppresses re-logging the same background geometry-preview failure on every retry
        # (initial_xyz_async() retries roughly every second while the input stays invalid).
        self._last_geometry_error = None
        self._last_geometry_exception = None

        self.normal_geometry = self.normalGeometry()

        import ssl
        ssl._create_default_https_context = ssl._create_stdlib_context

        try:
            if isinstance(filename, list):
                if re.match('https://|http://|file://', filename[0]):
                    self.project = Project(files=filename, **kwargs)
                else:
                    self.project = Project(location=(writable_directory(preferred=pathlib.Path(filename[0]).parent)),
                                           files=filename, **kwargs)
            elif pathlib.Path(filename).suffix == '.molpro':
                self.project = Project(filename, **kwargs)
            else:
                self.project = Project(
                    location=(writable_directory(preferred=pathlib.Path(filename).parent)),
                    files=[filename], **kwargs)
            logger.debug('Initialised Project input filename {}. Project bundle at {}'.format(filename,
                                                                                              self.project.filename('',
                                                                                                                    '',
                                                                                                                    -1)))
        except Exception as e:
            msg = QMessageBox()
            msg.setText('Project ' + str(filename) + ' cannot be opened')
            msg.setDetailedText(str(e))
            msg.exec()
            self.invalid = True
            return

        self.project.refresh_backends()
        self.ensure_local_molpro()

        settings['project_directory'] = os.path.dirname(self.project.filename(run=-1))

        self.discover_external_viewer_commands()

        self.input_pane = EditFile(self.project.filename('inp', run=-1), latency)
        self.setWindowTitle(self.project.filename(run=-1))

        self.input_specification = InputSpecification(self.input_pane.toPlainText(), directory=self.project.filename())

        self.vods = {}
        self.setup_menubar()

        self.run_button = QPushButton('Run job')
        self.run_button.clicked.connect(self.run_action.trigger)
        self.run_button.setToolTip("Run the job")

        self.statusBar = StatusBar(self.project, [self.run_action, self.run_button], [self.kill_action],
                                   run_lock=self._run_lock)
        self.statusBar.refresh()

        left_layout = QVBoxLayout()
        self.input_tabs = MyTabWidget(self)
        self.input_pane.textChanged.connect(lambda: self.thread_executor.submit(self.input_text_changed_consequence))
        self.input_tabs.currentChanged.connect(self.input_tab_changed_consequence)
        left_layout.addWidget(self.input_tabs)
        self.input_tabs.setMinimumHeight(300)
        self.input_tabs.setMinimumWidth(450)
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
        splitter = QSplitter(Orientation.Horizontal)
        top_layout.addWidget(splitter)

        left_widget = QWidget(self)
        left_widget.setContentsMargins(0, 0, 0, 0)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)
        self.output_tabs = OutputTabWidget(self)
        self.timer_output_tabs = QTimer(self)
        self.timer_output_tabs.timeout.connect(self.output_tabs.refresh)
        self.timer_output_tabs.timeout.connect(self.update_view_menu_actions)
        self.timer_output_tabs.start(1000)
        splitter.addWidget(self.output_tabs)
        splitter.setStretchFactor(1, 2147483647)

        self.layout = QVBoxLayout()
        self.layout.addLayout(top_layout)

        # self.minimum_window_size = self.window().size()

        if self.input_pane.toPlainText().strip('\n ') == '':
            self.input_pane.setPlainText(
                'geometry={0}.xyz\nbasis=cc-pV(T+d)Z-PP\ndf-rhf'.format(
                    os.path.basename(self.project.name).replace(' ', '-')))
            if not os.path.exists(self.project.filename('xyz')):
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

    def switch_run_directory(self, run: int):
        self.project.run_directory = run
        self.output_tabs.refresh()

    def ensure_local_molpro(self, search_MEIPASS=True):
        for path in os.environ['PATH'].split(os.pathsep):
            if (pathlib.Path(path) / 'molpro').is_file():
                return
            if platform.uname().system == 'Windows' and (pathlib.Path(path) / 'molpro.bat').is_file():
                return

        if hasattr(sys, '_MEIPASS') and search_MEIPASS:
            self.ensure_teaching_licence_accepted()

            s = str(pathlib.Path(sys._MEIPASS) / 'molpro' / 'bin')
            if s not in os.environ['PATH'].split(os.pathsep):
                os.environ['PATH'] += os.pathsep + s
                logger.debug(f'PATH appended with {s}')
                logger.debug(f'new PATH {os.environ["PATH"]}')
                self.ensure_local_molpro(search_MEIPASS=False)
                return

        msg = QMessageBox()
        msg.setText(f'Local molpro not found')
        msg.setDetailedText(f'PATH={os.environ["PATH"]}\nGuided mode will not work correctly.')
        msg.exec()

    def ensure_teaching_licence_accepted(self):
        licence_accepted_file = pathlib.Path.home() / '.molpro' / 'teaching_molpro_licence_accepted'
        try:
            user_name = pwd.getpwuid(os.getuid())[4].split(',')[0]
        except:
            user_name = 'User'
        licence_text = '1. Only educational use is permitted.\n2. Molpro, together with its documentation, is a copyrighted work of authorship,  and is licensed for use  by the user only. It may not be rented, leased, sub-licensed, sold or otherwise transferred to a third party.'
        licence_acceptance_text = user_name + ' has accepted the following conditions\n' + licence_text
        while not licence_accepted_file.is_file() or ''.join(
                open(licence_accepted_file).readlines()[1:]) != licence_acceptance_text:
            dlg = QMessageBox()
            dlg.setWindowTitle("Teaching Molpro licence")
            dlg.setText(
                "Molpro is necessary to use this program. You do not have a full copy of Molpro in your PATH. You can instead use the teaching version of Molpro embedded in this program, with limited functionality, but you must first agree to the following conditions.\n\n" + licence_text)
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dlg.setIcon(QMessageBox.Question)
            button = dlg.exec()
            if button != QMessageBox.Yes:
                logger.debug('licence not accepted; exiting')
                sys.exit(1)
            else:
                with open(licence_accepted_file, 'w') as f:
                    logger.debug('licence accepted: ' + licence_acceptance_text)
                    f.write(str(datetime.datetime.now()) + '\n')
                    f.write(licence_acceptance_text)
                logger.debug('Contents of ' + licence_accepted_file.as_posix() + ':\n' + ''.join(
                    open(licence_accepted_file).readlines()))

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

    def close(self):
        self.timer_output_tabs.stop()
        super().close()

    def setup_menubar(self):
        setup_project_window_menubar(self)

    def edit_backend_configuration(self):
        self.backend_configuration_editor = BackendConfigurationEditor(
            str(pathlib.Path.home() / '.sjef/molpro/backends.xml'), self)
        self.backend_configuration_editor.exec()

    def set_theme(self, theme_name):
        settings['theme'] = theme_name
        apply_theme(QApplication.instance(), theme_name)

    def guided_toggle(self):
        # logger.debug('guided_toggle')
        index = 1 if self.guided_action.isChecked() else 0
        if not self.guided_possible() and index == 1:
            box = QMessageBox()
            box.setText('Guided mode cannot be used because the input is too complex')
            spec_input = molpro_input.canonicalise(self.input_specification.molpro_input())
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
        # logger.debug('input_text_changed_consequence, index=' + str(index))
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
        # logger.debug('index=' + str(index) + ' ' + str(self.input_tabs.currentIndex()))
        if self.input_tabs.currentIndex() == 1:
            self.guided_pane.refresh()

    def available_functionals(self):
        project_registry = pymolpro.registry('dfunc')
        result = []
        if project_registry != None:
            for priority in range(5, -1, -1):
                for keyfound in project_registry:
                    if project_registry[keyfound]['priority'] == priority:
                        result.append(keyfound)
        return result

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
        molprorc = ''
        with open(pathlib.Path(self.project.filename(run=-1)) / 'molpro.rc', 'r') as f:
            molprorc = f.read()
        molprorc = molprorc.replace(' --xml-orbdump', '')
        # if 'orbitals' in self.input_specification:
        molprorc += ' --xml-orbdump'
        with open(pathlib.Path(self.project.filename(run=-1)) / 'molpro.rc', 'w') as f:
            f.write(molprorc)
        if self.guided_possible() and ('geometry' not in self.input_specification or (
                self.input_specification['geometry'][-4:] == '.xyz' and not os.path.exists(
            self.project.filename('', self.input_specification['geometry'], run=
            -1)))):
            QMessageBox.critical(self, 'Geometry missing', 'Cannot submit job because no geometry is defined')
            return False
        # project.run() blocks on network I/O for a remote backend (can take several seconds),
        # so it's submitted to the background thread pool rather than called here directly, to
        # keep the GUI responsive. The button/action are disabled meanwhile to prevent a second
        # submission racing the first, and completion is marshalled back to the GUI thread via
        # run_finished_signal (Qt widgets may only be touched from there, and plain
        # QTimer.singleShot() never fires when called from a thread with no Qt event loop).
        self.run_button.setEnabled(False)
        self.run_action.setEnabled(False)
        # Acquired here (not in submit_job) so it's already held by the time StatusBar's next
        # timer tick can fire, guaranteeing 'submitting' below can't be immediately clobbered by
        # a refresh() that snuck in before the background thread got going. It's released by
        # submit_job once the submission itself is done, so the next refresh() tick after that
        # naturally overwrites 'submitting' with the real status.
        self._run_lock.acquire()
        self.statusBar.setText('Status: submitting...')

        def submit_job():
            ld_library_path = os.environ.pop('LD_LIBRARY_PATH', None)
            error = None
            try:
                self.project.run(force=force, verbosity=int(os.environ.get('IMOLPRO_RUN_VERBOSITY', 0)))
                time.sleep(0.4)
            except Exception as e:
                error = e
            finally:
                self._run_lock.release()
            if ld_library_path is not None:
                os.environ['LD_LIBRARY_PATH'] = ld_library_path
            self.run_finished_signal.emit(error)

        self.thread_executor.submit(submit_job)
        return True

    def _run_submitted(self, error):
        self.run_button.setEnabled(True)
        self.run_action.setEnabled(True)
        if error is not None:
            QMessageBox.critical(self, 'Job submission failed', 'Cannot submit job:\n' + str(error))
            return
        self.switch_run_directory(len(self.project.run_directory_names) - 1)

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

    def show_xyz(self, instance=-1):
        for file in self.geometry_files():
            full_file = self.project.filename('', file[1], instance)
            # logger.debug('xyz file ' + full_file)
            with open(full_file, 'r') as f:
                contents = ''.join(f.readlines())
            # logger.debug('xyz file ' + contents)
            QMessageBox.information(self, 'xyz', contents)

    def show_xyz_input(self):
        self.show_xyz(-1)

    def show_xyz_output(self):
        self.show_xyz(0)
        pass

    def update_view_menu_actions(self):
        for suffix, action in getattr(self, 'view_file_actions', {}).items():
            try:
                filename = self.project.filename(suffix)
                exists = bool(filename) and os.path.isfile(filename) and os.path.getsize(filename) > 0
            except Exception:
                exists = False
            action.setEnabled(exists)
        for action, instance in getattr(self, 'view_xyz_actions', []):
            exists = False
            try:
                exists = any(
                    os.path.isfile(self.project.filename('', file[1], instance))
                    for file in self.geometry_files()
                )
            except Exception:
                exists = False
            action.setEnabled(exists)

    def visualise_input(self, external_path=None):
        # logger.debug('visualise_input' + str(self.vods.keys()))
        xyz_file = self.initial_xyz()
        if os.path.isfile(xyz_file):
            if external_path:
                subprocess.Popen([external_path, xyz_file])
            # elif 'builder' not in self.vods and 'initial structure' not in self.vods:
            #     print('visualise_input', xyz_file)
            # self.embedded_vod_jmol(xyz_file, command='', title='initial structure')

    def _initial_xyz_staleness(self):
        """
        Cheap (no subprocess) check of whether the cached initial-geometry xyz file is out of
        date with respect to the current input. Used by both initial_xyz() and
        initial_xyz_async() so the expensive recomputation in _compute_initial_xyz() can be
        gated without doing that work itself.

        Returns
        -------
        tuple[bool, str, str]
            (stale, xyz_file, geom)
        """
        geometry_directory = pathlib.Path(self.project.filename(run=-1)) / 'initial'
        geometry_directory.mkdir(exist_ok=True)
        xyz_file = str(geometry_directory / pathlib.Path(self.project.filename(run=-1)).stem) + '.xyz'
        # Deliberately re-parse the *current* input text here rather than relying on
        # self.input_specification: that attribute is only refreshed by
        # input_text_changed_consequence() when guided_possible() is true, so for input that
        # isn't representable in guided mode (eg an embedded Z-matrix using algebraic
        # parameters) it goes stale and can freeze on a 'geometry' value (or lack of one) left
        # over from before the edit, permanently suppressing regeneration of the input-structure
        # preview. Only actually re-parse when the text has changed since the last check --
        # this is called roughly once a second by initial_xyz_async(), and re-running the parse
        # when nothing changed is pure waste.
        current_text = self.input_pane.toPlainText()
        if current_text == self._initial_xyz_geom_cache[0]:
            geom = self._initial_xyz_geom_cache[1]
        else:
            try:
                geom = InputSpecification(current_text, directory=self.project.filename()).get('geometry', "")
            except Exception:
                # Falls back to the very attribute the comment above says goes stale -- only
                # acceptable because this is the rare/exceptional path (eg self.project.filename()
                # transiently raising), not the common one; log it so a persistent failure here
                # is diagnosable rather than silently masquerading as the bug this re-parse fixes.
                logger.debug('Failed to re-parse input pane text for initial-geometry staleness check',
                             exc_info=True)
                geom = self.input_specification.get('geometry', "")
            self._initial_xyz_geom_cache = (current_text, geom)
        if '.xyz' in geom and (not os.path.isfile(self.project.filename('', geom, run=-1)) or os.path.getsize(
                self.project.filename('', geom, run=-1)) <= 1):
            geom = ''
        stale = bool(geom) and (not os.path.isfile(xyz_file) or os.path.getmtime(xyz_file) < os.path.getmtime(
            self.project.filename('inp', run=-1)) or any(
            [os.path.getmtime(xyz_file) < os.path.getmtime(self.project.filename('', gfile[1], run=-1)) for gfile in
             self.geometry_files()]))
        return stale, xyz_file, geom

    def initial_xyz(self) -> str:
        """
        Generates or retrieves the XYZ file for the initial geometry configuration.

        This method handles the creation or validation of an XYZ file containing the system's initial geometry.
        It ensures that the file is either generated or updated as needed based on the current state of the
        input geometry and its associated files. Temporary directories and auxiliary computations are used
        where necessary to calculate or verify the geometric data. The method returns the path to the XYZ file,
        or an empty string if an error occurs during processing.

        This is a synchronous, potentially slow call (it can invoke Molpro) and is intended for
        explicit, on-demand use (eg the 'Visualise input' action). For periodic/background
        refreshes that must not block the calling (GUI) thread, use initial_xyz_async() instead.

        Parameters
        ----------
        None

        Returns
        -------
        str
            The file path to the generated or validated XYZ file. If an error occurs, an empty string is returned.
        """
        stale, xyz_file, geom = self._initial_xyz_staleness()
        if stale:
            with self._initial_xyz_lock:
                # re-check staleness now that we hold the lock, in case a background
                # recomputation (see initial_xyz_async()) already brought it up to date
                stale, xyz_file, geom = self._initial_xyz_staleness()
                if stale:
                    xyz_file = self._compute_initial_xyz(xyz_file)
        return xyz_file

    def initial_xyz_async(self) -> str:
        """
        Non-blocking counterpart to initial_xyz(), for use from periodic GUI-thread callbacks
        (eg OutputTabWidget.refresh(), which is driven by a 1-second QTimer). It never runs
        Molpro on the calling thread: the cheap staleness check happens immediately, and if
        recomputation is needed it is handed off to the background thread pool (and skipped
        entirely if a recomputation is already in flight), so the GUI stays responsive while
        editing the input even though the cached geometry is briefly out of date.

        Returns
        -------
        str
            The most recently computed xyz file path (which may be momentarily stale, or '' if
            none has been computed yet).
        """
        stale, xyz_file, geom = self._initial_xyz_staleness()
        if stale and self._initial_xyz_lock.acquire(blocking=False):
            def recompute():
                try:
                    self._compute_initial_xyz(xyz_file)
                    self._last_geometry_exception = None
                except Exception as e:
                    # This runs on a background thread via thread_executor and nothing ever
                    # calls .result() on the submitted future, so without this except clause
                    # any exception here (eg project.run() failing) would vanish silently -
                    # unlike the old synchronous code, where an uncaught exception at least
                    # produced a visible traceback via Qt's slot dispatch. While the input stays
                    # invalid this retries roughly once a second, so only log a given failure once
                    # rather than spamming an identical traceback every retry.
                    error_key = (type(e), str(e))
                    if error_key != self._last_geometry_exception:
                        self._last_geometry_exception = error_key
                        logger.exception('Background regeneration of the input-structure preview failed')
                finally:
                    self._initial_xyz_lock.release()

            self.thread_executor.submit(recompute)
        return xyz_file if os.path.isfile(xyz_file) else ''

    def _compute_initial_xyz(self, xyz_file) -> str:
        """
        Does the actual (expensive, Molpro-invoking) work of regenerating xyz_file. Safe to call
        from a background thread: it only touches the filesystem and Project/pymolpro objects,
        never Qt widgets. Callers are responsible for serializing access via _initial_xyz_lock.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdirname:
            path = pathlib.Path(tmpdirname) / 'input_geometries'
            os.makedirs(str(path), exist_ok=True)
            # logger.debug('visualise_input makes project at ' + str(path))
            self.project.copy(pathlib.Path(self.project.filename(run=-1)).name, location=path)
            project_path = path / pathlib.Path(self.project.filename(run=-1)).name
            project = Project(str(project_path))
            project.clean(0)
            open(project.filename('inp', run=-1), 'a').write('\nhf\n---')
            # logger.debug('visualise_input project input filename' + project.filename('inp', run=-1))
            # logger.debug('visualise_input project input file contents\n' + open(project.filename('inp', run=-1),'r').read())
            with open(pathlib.Path(project.filename(run=-1)) / 'molpro.rc', 'a') as f:
                f.write(' --geometry')

            ld_library_path = os.environ.pop('LD_LIBRARY_PATH', None)
            try:
                project.run(wait=True, force=True, backend='local')
                time.sleep(.3)  # not clear why this is needed
            except Exception:
                logger.warning('Error running Molpro to determine input geometry', exc_info=True)
            finally:
                if ld_library_path is not None:
                    os.environ['LD_LIBRARY_PATH'] = ld_library_path
            try:
                geometry = project.geometry()
            except Exception as e:
                # print(f"Error occurred while fetching geometry: {e}")
                geometry = None
            if not geometry:
                detail = ''
                for suffix in ['stdout', 'stderr', 'out']:
                    try:
                        with open(project.filename(suffix, run=0), 'r') as ff:
                            detail += ''.join(ff.readlines())
                    except:
                        pass
                try:
                    with open(project.filename('inp', run=-1), 'r') as ff:
                        preview_input = ff.read()
                except Exception:
                    preview_input = '<could not be read>'
                # While the input stays invalid this is retried roughly once a second (see
                # initial_xyz_async()), so only log a given failure once rather than repeatedly
                # dumping the full input/output at WARNING level for an unbounded retry loop.
                error_key = (preview_input, detail)
                if error_key != self._last_geometry_error:
                    self._last_geometry_error = error_key
                    logger.warning("Error in calculating input geometry for 'input structure' preview.\n"
                                   "Input:\n" + preview_input +
                                   "\nOutput/error detail:\n" + detail)
                # msg = QMessageBox()
                # msg.setIcon(QMessageBox.Critical)
                # msg.setWindowTitle("Error")
                # msg.setText('Error in calculating input geometry')
                # msg.setDetailedText(detail)
                # msg.exec_()
                xyz_file = ''
            else:
                self._last_geometry_error = None
                current_dir = os.path.dirname(self.project.filename(run=-1))
                project.trash()
                settings['project_directory'] = current_dir
                with open(xyz_file, 'w') as f:
                    f.write(str(len(geometry)) + '\n\n')
                    for atom in geometry:
                        f.write(atom['elementType'])
                        for c in atom['xyz']: f.write(' ' + str(c * .529177210903))
                        f.write('\n')
        return xyz_file

    def closeEvent(self, a0, QCloseEvent=None):
        for scene in self.findChildren(MoleculeScene):
            scene.Finalize()
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
            return filename

    def adopt_structure_file(self, filename):
        if os.path.exists(filename):
            self.project.import_file(filename)
            text = self.input_pane.toPlainText()
            if re.search(r'geometry *= *[-_./\w]+ *[;\n]', text, flags=re.IGNORECASE):
                self.input_pane.setPlainText(
                    re.sub('geometry *=.*[\n;]', 'geometry=' + os.path.basename(filename) + '\n', text))
            else:
                self.input_pane.setPlainText('geometry=' + os.path.basename(filename) + '\n' + text)
            self.xyz_to_zmat_activate_or_not(True)

    def database_import_structure(self):
        if filename := database_choose_structure():
            self.adopt_structure_file(filename)
            os.remove(filename)
            os.rmdir(os.path.dirname(filename))

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
                return filename

    def input_uses_xyz_file(self):
        if match := re.search(r'^ *geometry=(.*\.xyz)', self.input_pane.toPlainText(), re.MULTILINE):
            return match.group(1)
        else:
            return None

    def convert_xyz_to_zmat(self):
        if xyzfile := self.input_uses_xyz_file() is not None:
            zmat = pymolpro.xyz_to_zmat(self.project.filename('', xyzfile, -1))
            self.input_pane.setPlainText(
                self.input_pane.toPlainText().replace('geometry=' + xyzfile,
                                                      '!geometry=' + xyzfile + '\nangstrom\ngeometry={\n' + zmat + '}')
            )
        self.xyz_to_zmat_activate_or_not(False)

    def xyz_to_zmat_activate_or_not(self, activate: bool):
        for action in self.menuBar().actions():
            if action.text() == 'Files':
                for action2 in self.menuBar().findChildren(QAction, 'Convert xyz geometry to Z-matrix'):
                    action2.setEnabled(activate)

    def optimised_structure_files(self, run=0):
        run_directory_ = self.project.filename('', '', run)
        files = glob.glob('[Oo]ptimised*.xyz', root_dir=run_directory_)
        files_ = {}
        if 'optimised.xyz' in files: files_['final'] = 'optimised.xyz'
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
            self.close()
            self.__init__(file_name, self.window_manager, self.latency)

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
            time.sleep(.5)
            logger.debug('closing ' + self.project.filename(run=-1))
            self.close()
            logger.debug('closed ' + self.project.filename(run=-1))
            time.sleep(.5)
            self.project.trash()
            logger.debug('trashed ' + self.project.filename(run=-1))
            time.sleep(.5)
            settings['project_directory'] = current_dir
            logger.debug('save project_directory ' + current_dir)
            # self.close() (above) already unregistered this window and,
            # if it was the last open one, triggered the empty-window
            # action (Chooser.activate) -- but that happened before
            # trash() actually removed the project from disk, so the
            # recent-projects list it refreshed still showed the
            # about-to-be-erased project. Re-trigger it now that the
            # project is really gone.
            if self.window_manager.emptyAction and not self.window_manager.openWindows:
                self.window_manager.emptyAction()

    def show_input_specification(self):
        # self.input_specification is only refreshed when guided_possible() is true (see
        # _initial_xyz_staleness()), so re-parse the live text here rather than showing a
        # specification that may be stale for input not representable in guided mode.
        try:
            input_specification = InputSpecification(self.input_pane.toPlainText(), directory=self.project.filename())
        except Exception:
            input_specification = self.input_specification
        QMessageBox.information(self, 'Input specification', 'Input specification:\r\n' +
                                re.sub('}$', '\n}', re.sub('^{', '{\n  ', str(input_specification))).replace(', ',
                                                                                                             ',\n  '))
