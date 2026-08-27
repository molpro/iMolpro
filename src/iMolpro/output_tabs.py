import logging
import os

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QMainWindow, QApplication, QTabWidget, QWidget, QLabel, QVBoxLayout
    from PySide6.QtGui import QFont
except ImportError:
    try:
        from PyQt6.QtCore import QTimer, Qt
        from PyQt6.QtWidgets import QMainWindow, QApplication, QTabWidget, QWidget, QLabel, QVBoxLayout
        from PyQt6.QtGui import QFont
    except ImportError:
        from PyQt5.QtCore import QTimer, Qt
        from PyQt5.QtWidgets import QMainWindow, QApplication, QTabWidget, QWidget, QLabel, QVBoxLayout
        from PyQt5.QtGui import QFont

try:
    South = QTabWidget.TabPosition.South
except:
    South = QTabWidget.South

from .draggabletabwidget import DraggableTabWidget
from .utilities import ViewFile, atoms_from_xyz
from .vtk_molecule_widget import MoleculeDisplay

logger = logging.getLogger(__name__)


class ViewProjectOutput(ViewFile):
    def __init__(self, project, suffix='out', width=132, latency=100, filename_latency=500, point_size=8, instance=0):
        self.project = project
        self.suffix = suffix
        self.instance = instance
        minimum_point_size = point_size - 2
        # print('ViewProjectOutput',suffix,self.instance,self.project.filename(suffix,run=self.instance))
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
        try:
            latest_filename = self.project.filename(self.suffix, run=self.instance)
            if latest_filename != self.filename:
                self.reset(latest_filename)
        except:
            pass

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


class LazyOrbitalTab(QWidget):
    r"""Tab page standing in for an orbital-set MoleculeDisplay.

    Building a MoleculeDisplay for orbitals starts an (async, see
    vtk_molecule_widget._CubeWorker) orbital cube computation and sets up a
    whole VTK render window/interactor -- real cost that's wasted if the user
    never looks at that particular orbital set. A project's output can contain
    several orbital sets (canonical, natural, state-specific, ...), all
    discovered and added as tabs together in OutputTabWidget.refresh() as soon
    as they appear in the XML, so paying that cost eagerly for all of them
    means paying it for tabs that may never be selected. This placeholder
    defers building the real MoleculeDisplay until Qt actually shows this tab
    page, ie. the user selects it.
    """

    def __init__(self, orbitals, parent, metadata):
        super().__init__()
        self._orbitals = orbitals
        self._owner = parent
        self._metadata = metadata
        self.molecule_display = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel('Loading orbitals …', alignment=Qt.AlignCenter))

    def ensure_built(self):
        if self.molecule_display is not None:
            return
        layout = self.layout()
        while (item := layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()
        self.molecule_display = MoleculeDisplay(self._orbitals, self._owner, metadata=self._metadata)
        layout.addWidget(self.molecule_display)

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_built()


def force_render_vtk_widget(widget):
    if isinstance(widget, LazyOrbitalTab):
        widget.ensure_built()
        widget = widget.molecule_display
    if isinstance(widget, MoleculeDisplay):
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMainWindow):
                w.resize(w.width() + 1, w.height())
                w.repaint()
                w.resize(w.width() - 1, w.height())


class MyTabWidget(DraggableTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_names = set()
        self.currentChanged.connect(lambda: force_render_vtk_widget(self.currentWidget()))
        self.setTabBarAutoHide(True)
        self.setDocumentMode(True)
        self.setTabPosition(South)

    def addTab(self, widget, QWidget=None, *args, **kwargs):
        super().addTab(widget, QWidget, *args, **kwargs)
        if type(QWidget) is str:
            self.tab_names.add(QWidget)

    def indexOfTab(self, tab_name):
        for i in range(self.count()):
            if self.tabText(i) == tab_name:
                return i
        return -1

    def clear(self):
        self.tab_names.clear()
        super().clear()

    def __len__(self):
        return self.count()


class OutputTabWidget(MyTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.run_directory = None
        self.suffixes = {'inp', 'out', }
        self.refresh()

    def add_suffix(self, suffix):
        self.suffixes.add(suffix)
        self.refresh()
        self.setCurrentIndex(self.indexOfTab(self.label(suffix)))

    def del_suffix(self, suffix):
        self.suffixes.remove(suffix)

    def refresh(self):
        tab_names = [self.tabText(i) for i in range(self.count())]
        if self.run_directory != self.parent.project.run_directory:
            self.clear()
            self.run_directory = self.parent.project.run_directory
            self._xml_mtime = None
        # print('discover_tab_sources', run_directory)

        self.output_panes = {}
        for suffix in self.suffixes:
            if os.path.exists(filename := self.parent.project.filename(suffix, run=(
                    self.parent.project.run_directory))) and os.path.getsize(filename) > 0:
                label = self.label(suffix)
                # print('found',filename, label,os.path.getsize(filename) )
                if label not in tab_names:
                    self.addTab(ViewProjectOutput(self.parent.project, suffix, point_size=12 if suffix == 'inp' else 9,
                                                  width=80 if suffix == 'inp' else 132), label)

        # This method runs on a 1-second GUI-thread QTimer (see ProjectWindow.timer_output_tabs),
        # so re-parsing the whole XML file and re-enumerating every orbital set below (both
        # non-trivial for a large output) unconditionally on every tick was a periodic
        # ~1-second GUI-thread stall -- most noticeable as a stutter in the vibrational-mode
        # animation, since that's the one thing on screen fast enough to make a once-a-second
        # hitch obvious. Guard on the XML file's mtime (a cheap stat()) so that work only
        # actually happens when the file has changed since the last tick.
        xml_filename = self.parent.project.filename('xml', run=(self.parent.project.run_directory))
        xml_exists = os.path.exists(xml_filename) and os.path.getsize(xml_filename) > 0
        xml_mtime = os.path.getmtime(xml_filename) if xml_exists else None
        xml_changed = xml_mtime != getattr(self, '_xml_mtime', None)
        self._xml_mtime = xml_mtime

        if xml_exists and xml_changed:
            try:
                # get input geometry maybe
                # get final geometry
                final_structure = self.parent.project.structure(True)
                initial_structure = self.parent.project.structure(instance=0)
            except Exception as e:
                # Runs on a 1-second GUI-thread QTimer whenever the xml output file's mtime
                # changes, so while a job is actively running (output written incrementally) a
                # parse failure here could otherwise repeat every tick -- log a given failure
                # once rather than spamming an identical traceback on every retry.
                error_key = (type(e), str(e))
                if error_key != getattr(self, '_last_structure_parse_error', None):
                    self._last_structure_parse_error = error_key
                    logger.exception('Failed to parse structure(s) from %s', xml_filename)
                if 'initial_structure' not in locals(): initial_structure = None
                if 'final_structure' not in locals(): final_structure = None
            else:
                self._last_structure_parse_error = None
            # print('initial structure',initial_structure)
            # print('final structure',final_structure)
            final_structure_tab_label = 'final structure'
            initial_structure_tab_label = 'initial structure'
            if final_structure is not None and (not hasattr(self,
                                                            'final_structure') or self.final_structure != final_structure or final_structure_tab_label not in tab_names):
                self.final_structure = final_structure
                if final_structure_tab_label in tab_names:
                    self.removeTab(self.indexOfTab(final_structure_tab_label))
                # print('new tab','final structure', final_structure_tab_label)
                self.addTab(MoleculeDisplay(final_structure, self.parent), final_structure_tab_label)
            if initial_structure is not None and final_structure is None and initial_structure != final_structure and (
                    not hasattr(self,
                                'initial_structure') or self.initial_structure != initial_structure or initial_structure_tab_label not in tab_names):
                self.initial_structure = initial_structure
                if initial_structure_tab_label in tab_names:
                    self.removeTab(self.indexOfTab(initial_structure_tab_label))
                # print('new tab','initial structure', initial_structure_tab_label)
                self.addTab(MoleculeDisplay(initial_structure, self.parent), initial_structure_tab_label)

        # get input geometry from the input (non-blocking: this refresh() runs on a 1-second
        # GUI-thread QTimer, so we must never invoke Molpro synchronously here)
        input_xyz = self.parent.initial_xyz_async()
        if input_xyz:
            try:
                input_structure_tab_label = 'input structure'
                atoms = atoms_from_xyz(input_xyz)
                # print('self.initial_structure',self.initial_structure)
                test = 'initial_structure' in locals() and initial_structure is not None and atoms is not None
                if test:
                    for i, atom in enumerate(atoms):
                        test = test and all(
                            [abs(initial_structure.atoms[i]['xyz'][k] - atom['xyz'][k]) < 1e-7 for k in range(3)])
                if test:
                    if input_structure_tab_label in tab_names:
                        self.removeTab(self.indexOfTab(input_structure_tab_label))
                else:
                    if not hasattr(self,
                                   'input_atoms') or self.input_atoms != atoms or input_structure_tab_label not in tab_names:
                        # print('new input structure')
                        self.input_atoms = atoms
                        if input_structure_tab_label in tab_names:
                            self.removeTab(self.indexOfTab(input_structure_tab_label))
                        # print('new tab','input structure', input_structure_tab_label)
                        self.addTab(MoleculeDisplay(atoms, self.parent, metadata={'label': 'Input geometry'}),
                                    input_structure_tab_label)
            except:
                # raise Exception('Could not read input xyz file')
                pass

        if xml_exists and xml_changed:
            labels = {}
            try:
                for index in range(10000):  # get orbital sets
                    orbitals = self.parent.project.orbitals(index)
                    orbitals_node = orbitals[0].node.getparent()
                    label = orbitals_node.attrib['method'] + '/' + orbitals_node.attrib['type'] + ' orbitals'
                    if label in labels:
                        labels[label] += 1
                        label = label + ': ' + str(labels[label])
                    else:
                        labels[label] = 1
                    # print('found','orbital set', label)
                    if label not in tab_names:
                        # print('new tab','orbital set', label)
                        self.addTab(LazyOrbitalTab(orbitals, self, metadata=orbitals_node.attrib), label)
            except Exception as e:
                if not isinstance(e, (IndexError)) and not isinstance(e, (AttributeError)):
                    print('Orbitals except', str(e) + ' ' + str(type(e)))
                pass

    def label(self, suffix: str) -> str:
        return os.path.basename(self.parent.project.filename(suffix, run=(self.parent.project.run_directory)))
