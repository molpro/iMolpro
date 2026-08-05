import os

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMainWindow, QApplication, QTabWidget
    from PySide6.QtGui import QFont
except ImportError:
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QMainWindow, QApplication, QTabWidget
        from PyQt6.QtGui import QFont
    except ImportError:
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QMainWindow, QApplication, QTabWidget
        from PyQt5.QtGui import QFont

try:
    South = QTabWidget.TabPosition.South
except:
    South = QTabWidget.South

from .draggabletabwidget import DraggableTabWidget
from .utilities import ViewFile, atoms_from_xyz
from .vtk_molecule_widget import MoleculeDisplay


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


def force_render_vtk_widget(widget):
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

        if os.path.exists(filename := self.parent.project.filename('xml', run=(
                self.parent.project.run_directory))) and os.path.getsize(filename) > 0:
            try:
                # get input geometry maybe
                # get final geometry
                final_structure = self.parent.project.structure(True)
                initial_structure = self.parent.project.structure(instance=0)
            except:
                if 'initial_structure' not in locals(): initial_structure = None
                if 'final_structure' not in locals(): final_structure = None
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
            if initial_structure is not None and final_structure_tab_label not in tab_names and initial_structure != final_structure and (
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

        if os.path.exists(filename := self.parent.project.filename('xml', run=(
                self.parent.project.run_directory))) and os.path.getsize(filename) > 0:
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
                        self.addTab(MoleculeDisplay(orbitals, self,
                                                    metadata=orbitals_node.attrib,
                                                    ), label)
            except Exception as e:
                if not isinstance(e, (IndexError)) and not isinstance(e, (AttributeError)):
                    print('Orbitals except', str(e) + ' ' + str(type(e)))
                pass

    def label(self, suffix: str) -> str:
        return os.path.basename(self.parent.project.filename(suffix, run=(self.parent.project.run_directory)))
