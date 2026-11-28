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
from .vtk_molecule_widget import MoleculeDisplay, orbital_key

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


def _orbital_set_identity(orbitals, metadata):
    r"""What two orbital sets must share for one to stand in for the other: method, type and
    state, and the geometry of the molecule they belong to."""
    try:
        geometry = tuple(tuple(round(x, 5) for x in atom['xyz']) for atom in orbitals[0].atoms)
    except Exception:
        geometry = None
    return metadata.get('method'), metadata.get('type'), metadata.get('stateID'), geometry


def _orbital_signatures(orbitals) -> frozenset:
    return frozenset((orbital_key(orbital), round(getattr(orbital, 'energy', 0.0), 6),
                      round(getattr(orbital, 'occupation', 0.0), 6)) for orbital in orbitals)


def drop_contained_orbital_sets(sets: list) -> list:
    r"""
    `sets` (each a list starting with [orbitals, metadata, ...]) without those whose orbitals are
    all contained in another set of the same method, type, state and geometry.

    Molpro can write the same orbitals more than once, eg. the occupied orbitals of an SCF
    jobstep and, from a later ``put,xml``, the same orbitals together with the virtual ones. Only
    the most complete copy is kept (of identical copies, the first), in its original place.
    """
    described = [(_orbital_set_identity(s[0], s[1]), _orbital_signatures(s[0])) for s in sets]

    def contained(i):
        identity, signatures = described[i]
        return any(j != i and other_identity == identity and signatures <= other_signatures
                   and (len(signatures) < len(other_signatures) or j < i)
                   for j, (other_identity, other_signatures) in enumerate(described))

    return [s for i, s in enumerate(sets) if not contained(i)]


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
        # Keep the Runs menus in step with the project's run directories. (This is the only
        # periodic hook; the menus don't exist yet while this widget is first constructed.)
        run_directory_menus = getattr(self.parent, 'run_directory_menus', None)
        if run_directory_menus is not None:
            run_directory_menus.refresh()
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
            # Whether a final-structure tab exists *right now* -- not final_structure is None
            # (only this tick's read, which stays None on this run_directory once a final
            # structure has been read successfully in the past, so wrongly permits an
            # initial-structure tab alongside a final-structure tab added on an earlier tick;
            # nor the stale pre-tick tab_names snapshot (only reflects tabs added before this
            # tick, so wrongly permits both tabs on the very tick the final-structure tab is
            # first added above).
            final_structure_tab_present = self.indexOfTab(final_structure_tab_label) != -1
            if initial_structure is not None and not final_structure_tab_present and initial_structure != final_structure and (
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
            # Collect the orbital sets first: for UHF the alpha and beta orbitals arrive as two
            # separate <orbitals> nodes, which are shown together in a single tab.
            sets = []  # [orbitals, metadata, (instance, spin, method, stateID) while awaiting a partner, else None]

            def collect(instance):
                for index in range(10000):  # get orbital sets of this molecule node
                    try:
                        # every orbital, including virtual and weakly occupied ones
                        orbitals = self.parent.project.orbitals(instance, orbital_instance=index,
                                                                minocc=float('-inf'))
                    except (IndexError, AttributeError):
                        break
                    if not orbitals:
                        continue
                    orbitals_node = orbitals[0].node.getparent()
                    metadata = dict(orbitals_node.attrib)
                    spin = metadata.get('spin', '').lower()
                    if spin in ('alpha', 'beta'):
                        key = (instance, spin, metadata.get('method'), metadata.get('stateID'))
                        partner = next((s for s in sets if s[2] is not None and s[2][0] == instance
                                        and s[2][1] != spin and s[2][2:] == key[2:]), None)
                        if partner is not None:
                            # beta first, so that the alpha orbitals are the default (last) selection
                            partner[0] = orbitals + partner[0] if spin == 'beta' else partner[0] + orbitals
                            partner[1]['type'] = 'ALPHA+BETA'
                            partner[1].pop('spin', None)
                            partner[2] = None
                            continue
                        sets.append([orbitals, metadata, key])
                    else:
                        sets.append([orbitals, metadata, None])

            try:
                for instance in range(len(self.parent.project.xpath('//*/molecule'))):
                    collect(instance)
            except Exception as e:
                if not isinstance(e, (IndexError, AttributeError)):
                    print('Orbitals except', str(e) + ' ' + str(type(e)))
            sets = drop_contained_orbital_sets(sets)
            # spin-resolved (UHF) orbitals first, so they are what is shown by default
            sets.sort(key=lambda s: s[1].get('type') not in ('ALPHA', 'BETA', 'ALPHA+BETA'))
            for orbitals, metadata, _ in sets:
                label = metadata['method'] + '/' + metadata['type'] + ' orbitals'
                if label in labels:
                    labels[label] += 1
                    label = label + ': ' + str(labels[label])
                else:
                    labels[label] = 1
                if label not in tab_names:
                    self.addTab(LazyOrbitalTab(orbitals, self, metadata=metadata), label)

    def label(self, suffix: str) -> str:
        return os.path.basename(self.parent.project.filename(suffix, run=(self.parent.project.run_directory)))
