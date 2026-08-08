import os

import pikepdf
from pikepdf import PdfImage
from PIL import Image as PILImage
import math
import numpy as np
from pymolpro import Orbital

from .project import Structure
from .theme import LIGHT_GREY_WINDOW, DARK_GREY_WINDOW, THEMES, theme_manager
from .settings import settings
from .utilities import displace_coordinate

try:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
        QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
    from PySide6.QtCore import Qt, QSize, QTimer, QElapsedTimer
except ImportError:
    try:
        from PyQt6.QtGui import QColor, QPalette
        from PyQt6.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
            QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
        from PyQt6.QtCore import Qt, QSize, QTimer, QElapsedTimer
    except ImportError:
        from PyQt5.QtGui import QColor, QPalette
        from PyQt5.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
            QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
        from PyQt5.QtCore import Qt, QSize, QTimer, QElapsedTimer

try:
    ColorRole = QPalette.ColorRole
except:
    ColorRole = QPalette

from pymolpro.cube_data import CubeData
from ase.data import colors, covalent_radii, chemical_symbols
from pymolpro.elements import periodic_table
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkStringArray, vtkIntArray, vtkPoints, vtkFloatArray, vtkMath, \
    vtkMinimalStandardRandomSequence
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkImageData
from vtkmodules.vtkCommonMath import vtkMatrix4x4
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import vtkGlyph3D, vtkContourFilter
from vtk import vtkActor
from .QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from enum import Enum

from vtkmodules.vtkFiltersSources import vtkSphereSource, vtkCylinderSource
from vtkmodules.vtkIOExportGL2PS import vtkGL2PSExporter
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingAnnotation import vtkCubeAxesActor
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkLightKit, vtkActor2D, vtkActorCollection, vtkPolyDataMapper, \
    vtkColorTransferFunction, vtkTextProperty
from vtkmodules.vtkRenderingLabel import vtkPointSetToLabelHierarchy, vtkLabelPlacementMapper

# On VTK builds where they're compiled in (e.g. the official PyPI wheels),
# vtkContourFilter can be silently swapped at runtime for a Viskores
# (formerly VTK-m) accelerated implementation via VTK's object factory.
# That accelerated path logs an "INFO| Using flying edges" line to stderr
# every time CubeActor's vtkContourFilter runs, which is harmless but
# noisy. Explicitly disabling the override keeps vtkContourFilter on its
# ordinary (non-Viskores) code path, which doesn't emit that message.
# Older/minimal VTK builds don't ship this module at all, hence the guard.
try:
    from vtkmodules.vtkAcceleratorsVTKmFilters import vtkmFilterOverrides

    vtkmFilterOverrides.SetEnabled(False)
except ImportError:
    pass


class ColourScheme(Enum):
    dark = DARK_GREY_WINDOW.red(), DARK_GREY_WINDOW.green(), DARK_GREY_WINDOW.blue(),
    light = LIGHT_GREY_WINDOW.red(), LIGHT_GREY_WINDOW.green(), LIGHT_GREY_WINDOW.blue(),
    black = 0, 0, 0,
    white = 255, 255, 255,
    red = 255, 0, 0,
    green = 0, 255, 0,
    blue = 0, 0, 255,
    yellow = 255, 255, 0,
    cyan = 0, 255, 255,
    magenta = 255, 0, 255,
    orange = 255, 165, 0,
    purple = 128, 0, 128,
    brown = 165, 42, 42,


class StyledWidget(QWidget):
    def __init__(self, parent=None, background_colour: tuple | ColourScheme = ColourScheme.dark,
                 follow_theme: bool | None = None,
                 ):
        QWidget.__init__(self, parent)
        # True if this widget's background should track the app theme.
        # Defaults to auto-detecting from background_colour when not given
        # explicitly: True only if it's a ColourScheme member whose name is
        # itself a theme name (ColourScheme.dark/.light, as opposed to e.g.
        # ColourScheme.black). Callers that derive a plain RGB tuple from
        # some other theme-linked source (e.g. a snapshot of the parent's
        # current palette colour) should instead pass follow_theme
        # explicitly, since the tuple alone can't be told apart from a
        # deliberately-chosen fixed colour that just happens to match.
        if follow_theme is None:
            follow_theme = isinstance(background_colour, ColourScheme) and background_colour.name in THEMES
        self.follow_theme = follow_theme
        colour = background_colour.value if isinstance(background_colour, ColourScheme) else background_colour
        self._apply_background_colour(colour)
        theme_manager.themeChanged.connect(self._on_theme_changed)

    def _apply_background_colour(self, colour):
        self.background_colour = colour
        self.dark = sum(self.background_colour) / 3.0 < 128
        self.dark = (self.background_colour[0] * 0.299 + self.background_colour[1] * 0.587 + self.background_colour[
            2] * 0.114) / 255.0 < 0.5
        palette = QPalette()
        palette.setColor(ColorRole.Window, QColor(*self.background_colour))
        self.setAutoFillBackground(True)
        self.setPalette(palette)
        if self.dark:
            self.setStyleSheet("* { color: rgb(255,255,255); font-size: 10px }\n")
        else:
            self.setStyleSheet("* { color: rgb(0,0,0); font-size: 10px }\n")

    def _on_theme_changed(self, theme_name):
        if self.follow_theme and theme_name in THEMES:
            self._apply_background_colour(ColourScheme[theme_name].value)


class FixedLabel(QLabel):
    def __init__(self, text, parent=None):
        QLabel.__init__(self, text, parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class ItemLayout(QGridLayout):
    def __init__(self, parent=None):
        QGridLayout.__init__(self, parent)
        self.setContentsMargins(0, 0, 0, 0)
        # self.setSpacing(0)
        self.row = 0

    def add(self, title, content):
        self.addWidget(FixedLabel((title + ':') if title else ''), self.row, 0)
        if isinstance(content, QWidget):
            self.addWidget(content, self.row, 1)
        elif isinstance(content, QLayout):
            self.addLayout(content, self.row, 1, )
        self.row += 1
        return self.row - 1


class MoleculeDisplay(QWidget):
    def __init__(self, source: Structure | str | list, parent=None, axes: bool = False,
                 background_colour: tuple | ColourScheme | None = None,
                 contour_value=None, contour_opacity=None,
                 resolution: float = None,
                 metadata: dict = {},
                 ):
        settings.add_default('contour_value', .1)
        settings.add_default('contour_opacity', .7)
        settings.add_default('grid_resolution', .3)
        settings.add_default('vibrational_frequency_scaling', 1.0)
        if contour_value is None:
            contour_value = settings['contour_value']
            # print('MoleculeDisplay() sets contour_value',contour_value)
        else:
            settings['contour_value'] = contour_value
        if contour_opacity is None:
            contour_opacity = settings['contour_opacity']
        else:
            settings['contour_opacity'] = contour_opacity
        if resolution is None:
            resolution = settings['grid_resolution']
        else:
            settings['grid_resolution'] = resolution
        follow_theme = True if background_colour is None else None
        if background_colour is None:
            rgb = parent.palette().color(QPalette.Window).rgb()
            background_colour = (((rgb >> 16) & 0xFF), ((rgb >> 8) & 0xFF), (rgb & 0xFF))
        QWidget.__init__(self, parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.parent = parent

        self.metadata = metadata
        self.vibrational_mode = 0
        self.vibration_animating = False
        self._vibration_timer = None

        if isinstance(source, list) and len(source) > 0 and isinstance(source[-1], dict):
            data = source
        elif isinstance(source, Structure):
            data = source
            if source.vibrations and source.vibrations.modes:
                metadata['vibrations'] = source.vibrations
                self._equilibrium_atoms = source.atoms
        elif isinstance(source, list) and len(source) > 0 and isinstance(source[-1], Orbital):
            self.cubes = {}
            self.orbitals = source
            self.resolution = resolution
            self.orbital = source[-1]
            data = self.get_cube(contour_value=contour_value)
        else:
            raise ValueError('source must be a list of Orbitals or a dict of atoms or an xyz filename')

        self.molecule_widget = MoleculeWidget(data, self, background_colour=background_colour, sliders=False,
                                              contour_value=contour_value,
                                              contour_opacity=contour_opacity, follow_theme=follow_theme)
        layout.addWidget(self.molecule_widget)

        self.right_panel = ControlPanel(self, metadata=metadata)
        layout.addWidget(self.right_panel)

    def get_cube(self, contour_value=None):
        # print('get_cube',self.orbital.ID,self.resolution,contour_value,'')
        key = self.orbital, self.resolution, contour_value
        if key not in self.cubes:
            # print('get_cube',self.orbital.ID,self.resolution,contour_value,'creating')
            self.cubes[key] = self.orbital.cube_data(resolution=self.resolution, threshold=contour_value * .1, border=6)
        return self.cubes[key]

    def set_atom_labels(self, atom_labels: bool):
        self.molecule_widget.show_nucleus_labels(atom_labels)

    def set_orbital(self, orbital_id):
        # print('set_orbital', orbital_id)
        self.orbital = self.orbitals[[orbital.ID for orbital in self.orbitals].index(orbital_id)]
        cube_data = self.get_cube(self.molecule_widget.model.contour_value)
        # print(str(cube_data)[:100] + '...')
        self.right_panel.refresh()
        self.molecule_widget.refresh_model(cube_data)
        pass

    def set_vibration(self, mode_index):
        self.vibrational_mode = mode_index
        self.right_panel.refresh()
        if self.vibration_animating:
            self._start_vibration_animation()

    # Per-atom displacement (bohr) at the peak of the oscillation. Chosen to
    # be a visible fraction of a typical bond length without atoms swinging
    # through each other, regardless of the (implementation-defined) scale
    # of the raw normal-coordinate vectors coming from the XML.
    VIBRATION_PEAK_DISPLACEMENT = 0.4
    VIBRATION_FRAME_INTERVAL_MS = 33
    # Range of the 'Speed' slider (a multiplier on the nominal 1000cm-1 <-> 1Hz mapping).
    # Capped at 1.0 -- the slider is there to slow the animation down to something the
    # renderer can keep up with, not to speed it up further.
    VIBRATION_SPEED_SLIDER_MINIMUM = 0.05
    VIBRATION_SPEED_SLIDER_MAXIMUM = 1.0
    # Sphere tessellation while animating: dropped right down, since vtkGlyph3D pays this
    # cost fresh on every frame (see NucleiActor.set_source). Restored to
    # NucleiActor.STATIC_SPHERE_RESOLUTION -- full quality -- as soon as animation stops,
    # eg. for a static-structure image export.
    VIBRATION_ANIMATING_SPHERE_RESOLUTION = 24

    def set_vibration_animate(self, animate: bool):
        self.vibration_animating = animate
        if animate:
            self._start_vibration_animation()
        else:
            self._stop_vibration_animation()

    def set_vibration_frequency_scaling(self, slider_value: int):
        r"""Live-adjust the animation speed (see the 'Speed' slider, values 0-100), without resetting amplitude or restarting the timer. Re-baselines the oscillation phase against the new frequency so the motion doesn't jump when the scaling changes mid-animation."""
        scaling = self.VIBRATION_SPEED_SLIDER_MINIMUM * math.exp(
            slider_value * 0.01 * math.log(
                self.VIBRATION_SPEED_SLIDER_MAXIMUM / self.VIBRATION_SPEED_SLIDER_MINIMUM))
        settings['vibrational_frequency_scaling'] = scaling
        if self.vibration_animating and hasattr(self, '_vibration_base_omega'):
            self._vibration_phase0 = self._current_vibration_phase()
            self._vibration_t0 = self._vibration_clock.elapsed() / 1000.0
            self._vibration_omega = self._vibration_base_omega * scaling

    def _current_vibration_phase(self):
        t = self._vibration_clock.elapsed() / 1000.0
        return self._vibration_phase0 + self._vibration_omega * (t - self._vibration_t0)

    def _start_vibration_animation(self):
        vibrations = self.metadata.get('vibrations')
        if not vibrations or not vibrations.modes or not hasattr(self, '_equilibrium_atoms'):
            return
        mode = vibrations.modes[self.vibrational_mode]
        vector = mode['vector']
        n_atoms = len(vector) // 3
        peak_norm = max(
            (math.sqrt(sum(vector[3 * i + k] ** 2 for k in range(3))) for i in range(n_atoms)),
            default=0.0,
        )
        self._vibration_vector = vector
        self._vibration_amplitude = self.VIBRATION_PEAK_DISPLACEMENT / peak_norm if peak_norm > 1e-8 else 0.0
        # 1000 cm-1 <-> 1 oscillation/sec, i.e. frequency_Hz = wavenumber / 1000, further
        # scaled by the user-adjustable 'Speed' slider (settings['vibrational_frequency_scaling'])
        self._vibration_base_omega = 2 * math.pi * mode['wavenumber'] / 1000.0
        self._vibration_omega = self._vibration_base_omega * float(settings['vibrational_frequency_scaling'])
        self._vibration_phase0 = 0.0
        self._vibration_t0 = 0.0
        self._vibration_clock = QElapsedTimer()
        self._vibration_clock.start()
        self.molecule_widget.model.geometry.set_sphere_resolution(self.VIBRATION_ANIMATING_SPHERE_RESOLUTION)
        if self._vibration_timer is None:
            self._vibration_timer = QTimer(self)
            self._vibration_timer.timeout.connect(self._advance_vibration_animation)
        self._vibration_timer.start(self.VIBRATION_FRAME_INTERVAL_MS)

    def _advance_vibration_animation(self):
        displacement = self._vibration_amplitude * math.sin(self._current_vibration_phase())
        atoms = displace_coordinate(self._equilibrium_atoms, self._vibration_vector, displacement)
        self.molecule_widget.update_geometry(atoms)

    def _stop_vibration_animation(self):
        if self._vibration_timer is not None:
            self._vibration_timer.stop()
        if hasattr(self, '_equilibrium_atoms'):
            self.molecule_widget.model.geometry.set_sphere_resolution(NucleiActor.STATIC_SPHERE_RESOLUTION)
            self.molecule_widget.update_geometry(self._equilibrium_atoms)

    def hideEvent(self, event):
        # Pause the animation timer while this tab isn't visible so a
        # replaced/hidden MoleculeDisplay (see MyTabWidget.removeTab, which
        # doesn't delete the old widget) doesn't keep re-rendering forever.
        if self._vibration_timer is not None:
            self._vibration_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self.vibration_animating and self._vibration_timer is not None:
            self._vibration_clock.start()
            self._vibration_timer.start(self.VIBRATION_FRAME_INTERVAL_MS)

    def set_resolution(self, resolution):
        shift_factor = 0.8
        if type(resolution) is int:
            resolution = resolution / 100.0
        elif type(resolution) is str and resolution == '+':
            resolution = self.resolution * shift_factor
        elif type(resolution) is str and resolution == '-':
            resolution = self.resolution / shift_factor

        # print('set_resolution', resolution)
        self.resolution = resolution
        self.set_orbital(self.orbital.ID)


class MoleculeWidget(StyledWidget):
    def _on_theme_changed(self, theme_name):
        super()._on_theme_changed(theme_name)
        if self.follow_theme and theme_name in THEMES:
            self.scene.SetBackground(*[c / 255.0 for c in self.background_colour])
            self.scene.GetRenderWindow().GetInteractor().Render()

    def refresh_model(self, source):
        # print('refresh_model', type(source))
        # print('self.model', type(self.model))
        self.scene.Remove(self.model.contour)
        self.model = MolecularModel(source, )
        self.scene.Add(self.model.contour)
        self.scene.GetRenderWindow().GetInteractor().Render()

    def show_nucleus_labels(self, show: bool):
        self.nucleus_labels.SetVisibility(show)
        self.scene.GetRenderWindow().GetInteractor().Render()

    def update_geometry(self, atoms: list[dict]):
        r"""Reposition the nuclei/bond actors (and, if shown, the atom-label actor) to a new set of atomic coordinates, without rebuilding the whole model. Used for vibrational-mode animation."""
        self.model.geometry.update(atoms)
        if self.nucleus_labels.GetVisibility():
            self.nucleus_labels.update(atoms)
        self.scene.GetRenderWindow().GetInteractor().Render()

    def __init__(self, source, parent=None, axes: bool = False,
                 background_colour: tuple | ColourScheme = ColourScheme.dark,
                 contour_value=.1, contour_opacity=.7,
                 sliders: bool = True, follow_theme: bool | None = None,
                 ):
        StyledWidget.__init__(self, parent, background_colour=background_colour, follow_theme=follow_theme)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.scene = MoleculeScene(self)
        self.model = MolecularModel(source, contour_value=contour_value, contour_opacity=contour_opacity,
                                    bond_colour=(0.8, 0.8, 0.8) if self.dark else (0.6, 0.6, 0.6))
        self.scene.Add(self.model)
        if isinstance(source, Structure):
            source_ = source.atoms
        else:
            source_ = source
        self.nucleus_labels = NucleusLabelsActor(source_)
        self.show_nucleus_labels(False)
        self.scene.Add(self.nucleus_labels)
        self.scene.SetBackground(*[c / 255.0 for c in self.background_colour])
        if axes:
            self.add_axes(self.scene)

        layout.addWidget(self.scene)

        self.contour_slider_minimum = 0.003
        self.contour_slider_maximum = 0.5
        if sliders and hasattr(self.model, 'contour'):
            slider_layout = QGridLayout()
            slider_layout.addWidget(QLabel('Contour:'), 0, 0)
            layout.addLayout(slider_layout)
            opacity_slider = mySlider(self)
            opacity_slider.valueChanged.connect(self.set_contour_opacity)
            opacity_slider.setValue(int(self.model.contour.opacity * 100))
            slider_layout.addWidget(QLabel('Opacity'), 0, 1)
            slider_layout.addWidget(opacity_slider, 0, 2)

            contour_slider = mySlider(self)
            contour_slider.valueChanged.connect(self.set_contour_value)
            contour_slider.setValue(
                int(100 * math.log(self.model.contour_value / self.contour_slider_minimum) / math.log(
                    self.contour_slider_maximum / self.contour_slider_minimum)))
            slider_layout.addWidget(QLabel('Value'), 0, 3)
            slider_layout.addWidget(contour_slider, 0, 4)

        self.show()

        self.scene.start()

    @property
    def contour_opacity(self):
        return self.model.contour.opacity

    def set_contour_opacity(self, value):
        self.model.set_contour_opacity(value * 0.01)
        settings['contour_opacity'] = self.model.contour.opacity
        self.scene.GetRenderWindow().GetInteractor().Render()

    @property
    def contour_value(self):
        return self.model.contour_value

    def set_contour_value(self, value):
        contour_value = self.contour_slider_minimum * math.exp(
            value * 0.01 * math.log(self.contour_slider_maximum / self.contour_slider_minimum))
        self.model.set_contour_value(contour_value)
        settings['contour_value'] = self.model.contour_value
        self.scene.GetRenderWindow().GetInteractor().Render()

    def set_background_colour(self, colour: QColor | int | tuple[float, float, float], follow_theme: bool = False):
        # print('set_background_colour', colour,type(colour))
        if type(colour) is int:
            colour = QColor(colour)
        if type(colour) is QColor:
            if not colour.isValid(): return
            rgb = colour.rgb()
            blue = rgb & 0xFF
            green = (rgb >> 8) & 0xFF
            red = (rgb >> 16) & 0xFF
            # print('set_background_colour', rgb,red,green,blue)
            return self.set_background_colour((red, green, blue), follow_theme=follow_theme)
        self.follow_theme = follow_theme
        self.background_colour = colour
        self.scene.SetBackground(*[c / 255.0 for c in self.background_colour])
        self.scene.GetRenderWindow().GetInteractor().Render()

    def add_axes(self, scene):
        axes = vtkCubeAxesActor()

        # 2. Configure the bounds (e.g., -10 to 10 for X, Y, and Z)
        # This ensures the axes "pass through" the origin contextually
        axes.SetBounds(-4, 4, -4, 4, -4, 4)

        # 3. Set the Camera (Required for label orientation)
        # renderer = vtk.vtkRenderer()
        renderer = scene.renderer
        axes.SetCamera(renderer.GetActiveCamera())

        # 4. Customise Ticks and Labels
        axes.SetXTitle("X")
        axes.SetYTitle("Y")
        axes.SetZTitle("Z")
        axes.GetTitleTextProperty(0).SetColor(1, 0, 0)  # Red X title
        axes.SetTickLocationToBoth()  # Ticks on both sides of the line
        axes.DrawXGridlinesOn()
        axes.DrawYGridlinesOn()
        axes.DrawZGridlinesOn()
        scene.Add(axes)


class ControlPanel(QWidget):
    def __init__(self, parent, metadata={}):
        super().__init__(parent)
        self.parent = parent
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setup(metadata=metadata)
        self.refresh()

    def refresh(self):
        if hasattr(self, 'energy_widget'):
            if hasattr(self.parent.orbital, 'energy'):
                self.energy_widget.setText(str(self.parent.orbital.energy))
            else:
                self.energy_widget.setText('None')
        if hasattr(self, 'occupation_widget'):
            if hasattr(self.parent.orbital, 'occupation'):
                self.occupation_widget.setText(str(self.parent.orbital.occupation))
            else:
                self.occupation_widget.setText('None')
        pass

    def setup(self, metadata={}):

        while w := self.findChild(QWidget):
            w.setParent(None)

        if 'vibrations' in metadata:
            self.layout.addWidget(QLabel('Vibrations'),
                                  alignment=Qt.AlignCenter)
        if 'method' in metadata and 'type' in metadata:
            self.layout.addWidget(QLabel(f'{metadata["method"]}/{metadata["type"]} orbitals'),
                                  alignment=Qt.AlignCenter)
            if 'state_symmetry' in metadata and 'stateID' in metadata:
                title = 'State ' + metadata['state_symmetry'] + '.' + str(metadata['stateID'])
                if 'state_ms2' in metadata:
                    ms2 = int(metadata['state_ms2'])
                    title = title + ', spin ' + (str(ms2 // 2) if ms2 % 2 == 0 else str(ms2) + '/2')
                self.layout.addWidget(QLabel(title), alignment=Qt.AlignCenter)

        self.control_layout = ItemLayout()
        self.layout.addLayout(self.control_layout)
        self.layout.addStretch()
        # self.control_layout.addWidget(QLabel('Orbitals'),0,0)

        if 'vibrations' in metadata and metadata['vibrations'].modes:
            vibration_selector = QComboBox()
            for i, mode in enumerate(metadata['vibrations'].modes):
                vibration_selector.addItem(f'{i + 1}: {mode["wavenumber"]} cm-1')
            vibration_selector.setCurrentIndex(self.parent.vibrational_mode)
            vibration_selector.currentIndexChanged.connect(self.parent.set_vibration)
            self.control_layout.add('Normal mode', vibration_selector)

            animate_checkbox = QCheckBox()
            animate_checkbox.setChecked(self.parent.vibration_animating)
            animate_checkbox.toggled.connect(self.parent.set_vibration_animate)
            self.control_layout.add('Animate', animate_checkbox)

            speed_slider = mySlider(self)
            speed_slider.setValue(int(100 * math.log(
                float(settings['vibrational_frequency_scaling']) / self.parent.VIBRATION_SPEED_SLIDER_MINIMUM) /
                                     math.log(self.parent.VIBRATION_SPEED_SLIDER_MAXIMUM /
                                             self.parent.VIBRATION_SPEED_SLIDER_MINIMUM)))
            speed_slider.valueChanged.connect(self.parent.set_vibration_frequency_scaling)
            self.control_layout.add('Speed', speed_slider)
        if hasattr(self.parent, 'orbitals'):
            orbital_selector = QComboBox()
            for orbital in self.parent.orbitals[::-1]:
                orbital_selector.addItem(str(orbital.ID))
            orbital_selector.currentTextChanged.connect(self.parent.set_orbital)
            # orbital_selector.setBackgroundColor(QColor(*self.background_colour))
            # palette = self.palette()
            # palette.setColor(QPalette.Base, QColor(*self.background_colour))
            # palette.setColor(QPalette.Base, QColor('Red'))
            # orbital_selector.setPalette(palette)
            # orbital_selector.setAutoFillBackground(True)
            orbital_selector.setMinimumWidth(orbital_selector.minimumSizeHint().width())
            self.control_layout.add('Orbital', orbital_selector)

            if hasattr(self.parent.orbital, 'occupation'):
                row = self.control_layout.add('Occupation', QLabel(str(self.parent.orbital.occupation)))
                self.occupation_widget = self.control_layout.itemAtPosition(row, 1).widget()

            if hasattr(self.parent.orbital, 'energy'):
                row = self.control_layout.add('Energy', QLabel(str(self.parent.orbital.energy)))
                self.energy_widget = self.control_layout.itemAtPosition(row, 1).widget()

            # self.control_layout.addWidget(FixedLabel('Contour:'), row, 0)
            contour_slider = mySlider(self)
            self.contour_slider_minimum = 0.003
            self.contour_slider_maximum = 0.5
            contour_slider.valueChanged.connect(self.parent.molecule_widget.set_contour_value)
            contour_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
            contour_slider.setValue(
                int(100 * math.log(
                    float(settings['contour_value']) / self.contour_slider_minimum) / math.log(
                    self.contour_slider_maximum / self.contour_slider_minimum)))
            self.control_layout.add('Contour value', contour_slider)

            opacity_slider = mySlider(self)
            opacity_slider.valueChanged.connect(self.parent.molecule_widget.set_contour_opacity)
            opacity_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
            opacity_slider.setValue(int(float(settings['contour_opacity']) * 100))
            self.control_layout.add('Opacity', opacity_slider)

            if False:
                resolution_slider = mySlider(self)
                resolution_slider.valueChanged.connect(self.set_resolution)
                resolution_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
                resolution_slider.setValue(int(self.resolution * 100))
                resolution_label = FixedLabel('Resolution:')
                self.control_layout.addWidget(resolution_label, row, 0)
                self.control_layout.addWidget(resolution_slider, row, 1)
                row += 1

            resolution_label = FixedLabel('Resolution:')
            resolution_layout = QHBoxLayout()
            # resolution_layout.setContentsMargins(0,0,0,0)
            # resolution_layout.setSpacing(0)
            coarser_button = QPushButton('-')
            resolution_layout.addWidget(coarser_button)
            coarser_button.clicked.connect(lambda: self.parent.set_resolution('-'))
            finer_button = QPushButton('+')
            resolution_layout.addWidget(finer_button)
            finer_button.clicked.connect(lambda: self.parent.set_resolution('+'))
            self.control_layout.add('Resolution', resolution_layout)

        # self.control_layout.add('',None)
        # print('adding stretch to row',self.control_layout.row)
        # self.control_layout.setRowStretch(self.control_layout.row, 999)
        atom_labels_checkbox = QCheckBox()
        self.control_layout.add('Atom labels', atom_labels_checkbox)
        atom_labels_checkbox.clicked.connect(lambda: self.parent.set_atom_labels(atom_labels_checkbox.isChecked()))

        colour_selection = QWidget(self)
        colour_selection_layout = QVBoxLayout()
        colour_selection_layout.setContentsMargins(0, 0, 0, 0)
        colour_selection.setLayout(colour_selection_layout)
        colour_selection_layout2 = QHBoxLayout()
        colour_selection_layout2.setContentsMargins(0, 0, 0, 0)
        colour_selection_layout.addLayout(colour_selection_layout2)
        # Every key in THEMES must have a matching ColourScheme member (see
        # ColourScheme[name] below) -- adding a new theme to theme.py also
        # needs a same-named entry added to ColourScheme.
        for i, name in enumerate(list(THEMES.keys()) + ['black', 'white']):
            # print('ColourScheme', name, ': ', ColourScheme[name].value)
            # button = QPushButton('')
            button = QToolButton(self)
            button.setMaximumSize(QSize(15, 15))
            mid = button.palette().color(ColorRole.Mid)
            button.setStyleSheet(
                f'background-color: rgb{str(ColourScheme[name].value)}; '
                f'border: 1px solid rgb({mid.red()},{mid.green()},{mid.blue()});')
            colour_selection_layout2.addWidget(button)
            button.clicked.connect(
                lambda checked, name=name: self.parent.molecule_widget.set_background_colour(
                    ColourScheme[name].value, follow_theme=(name in THEMES)))
        button = QPushButton('Other...')
        i += 1
        colour_selection_layout.addWidget(button)
        button.clicked.connect(lambda: self.parent.molecule_widget.set_background_colour(
            QColorDialog.getColor(initial=QColor(*self.parent.molecule_widget.background_colour), parent=self,
                                  title='Choose background colour')))
        self.control_layout.add('Background colour', colour_selection)

        export_button = QPushButton('Choose file')
        self.control_layout.add('Export image', export_button)
        export_button.clicked.connect(lambda: self.parent.molecule_widget.scene.export_image())

        # self.control_layout.addStretch()


class MoleculeScene(QVTKRenderWindowInteractor):

    def __init__(self, parent=None):
        QVTKRenderWindowInteractor.__init__(self, parent)
        self.renderer = vtkRenderer()
        self.renderer.AutomaticLightCreationOff()
        light_kit = vtkLightKit()
        light_kit.AddLightsToRenderer(self.renderer)
        light_kit.SetKeyLightWarmth(0.5)
        light_kit.SetKeyLightIntensity(0.9)
        # light_kit.SetKeyToFillRatio(2.0)
        self.GetRenderWindow().AddRenderer(self.renderer)
        self.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self.Initialize()

    def Add(self, source):
        if isinstance(source, vtkActor2D):
            self.renderer.AddActor2D(source)
        elif isinstance(source, vtkActor):
            self.renderer.AddActor(source)
        elif isinstance(source, vtkActorCollection):
            for actor in source:
                self.Add(actor)

    def Remove(self, source: vtkActor):
        self.renderer.RemoveActor(source)

    def SetBackground(self, r, g, b):
        self.renderer.SetBackground(r, g, b)

    def start(self):
        self.renderer.ResetCamera()
        self.GetRenderWindow().Render()
        self.Start()

    def export_image(self, filename: str = None):
        pdf_exporter = vtkGL2PSExporter()
        pdf_exporter.SetRenderWindow(self.GetRenderWindow())
        pdf_exporter.SetFileFormatToPDF()
        if filename is None:
            filename = os.path.splitext(QFileDialog.getSaveFileName(self, 'Export image', '', 'PDF (*.pdf)')[0])[0]
            if filename is None or filename == '':
                return
        pdf_exporter.SetFilePrefix(filename)
        renderer = self.GetRenderWindow().GetRenderers().GetFirstRenderer()
        background_rgb = tuple(round(c * 255) for c in renderer.GetBackground())
        pdf_exporter.Write()
        # vtkOpenGLGL2PSExporter always draws the background regardless of
        # DrawBackground (confirmed by VTK's own runtime warning) -- and,
        # for a 3D scene like this, the exported PDF turns out to contain
        # the whole rendered frame as a single embedded raster image, not
        # vector geometry with a separately-removable background rectangle
        # (GL2PS's vector capture only works with old fixed-function
        # OpenGL; VTK's modern OpenGL2 backend falls back to a raster
        # embed). Colour-key that image against the actual background
        # colour to build an alpha channel instead, and attach it as a
        # proper PDF soft mask.
        pdf_path = filename + '.pdf'
        if os.path.isfile(pdf_path):
            _make_pdf_background_transparent(pdf_path, background_rgb)


def _make_pdf_background_transparent(pdf_path, background_rgb, tol=10):
    """Make a GL2PS-exported PDF's background transparent.

    The exported PDF contains the whole rendered frame as a single embedded
    raster image (confirmed by inspecting a real export's content stream:
    just 'gs', 'q', 'cm', 'Do', 'Q' -- one image XObject scaled to cover the
    page, no vector background rectangle to strip). Colour-keys that image
    against `background_rgb` (an (r, g, b) tuple, 0-255) to build an 8-bit
    grayscale alpha channel -- background-coloured pixels (within `tol`)
    become transparent, everything else stays opaque -- and attaches it to
    the image XObject as a PDF soft mask (/SMask), which PDF viewers use to
    render per-pixel transparency for that image.

    Also declares the page as an isolated transparency group (/Group with
    /S /Transparency and /I true). Without this, some standalone PDF
    viewers (confirmed: macOS Preview, GIMP/poppler) still show an opaque
    white page background despite the image's own alpha being correct --
    they composite the page against an assumed opaque-white backdrop unless
    the page itself declares that its own backdrop should be treated as
    transparent. Other applications (confirmed: PowerPoint, Keynote) render
    the transparency correctly either way, apparently treating a
    single-image PDF more like importing a transparent picture regardless
    of this declaration.

    Best-effort: any exception, or no embedded image found on the page,
    leaves the PDF unchanged and returns False rather than risk corrupting
    the file.
    """
    try:
        with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            page = pdf.pages[0]
            images = page.images
            if not images:
                return False
            _, raw_image_obj = next(iter(images.items()))
            pil_img = PdfImage(raw_image_obj).as_pil_image().convert('RGB')
            arr = np.array(pil_img)
            r, g, b = background_rgb
            mask = (
                    (np.abs(arr[:, :, 0].astype(int) - r) <= tol) &
                    (np.abs(arr[:, :, 1].astype(int) - g) <= tol) &
                    (np.abs(arr[:, :, 2].astype(int) - b) <= tol)
            )
            alpha = np.where(mask, 0, 255).astype(np.uint8)
            alpha_img = PILImage.fromarray(alpha, mode='L')

            smask_stream = pdf.make_stream(alpha_img.tobytes())
            smask_stream.Type = pikepdf.Name('/XObject')
            smask_stream.Subtype = pikepdf.Name('/Image')
            smask_stream.Width = alpha_img.width
            smask_stream.Height = alpha_img.height
            smask_stream.ColorSpace = pikepdf.Name('/DeviceGray')
            smask_stream.BitsPerComponent = 8

            raw_image_obj.SMask = smask_stream

            page.Group = pikepdf.Dictionary(
                Type=pikepdf.Name('/Group'),
                S=pikepdf.Name('/Transparency'),
                CS=pikepdf.Name('/DeviceRGB'),
                I=True,
            )

            pdf.save(pdf_path)
            return True
    except Exception:
        return False


class mySlider(QSlider):
    def __init__(self, parent=None):
        QSlider.__init__(self, parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setOrientation(Qt.Horizontal)
        self.setStyleSheet("""
        mySlider::groove:horizontal {
border: 1px solid #bbb;
background: white;
height: 3px;
border-radius: 4px;
}

mySlider::sub-page:horizontal {
background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,
    stop: 0 #66e, stop: 1 #bbf);
background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,
    stop: 0 #bbf, stop: 1 #55f);
border: 1px solid #777;
height: 10px;
border-radius: 4px;
}

mySlider::add-page:horizontal {
background: #fff;
border: 1px solid #777;
height: 10px;
border-radius: 4px;
}

mySlider::handle:horizontal {
background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #eee, stop:1 #ccc);
border: 1px solid #777;
width: 13px;
margin-top: -2px;
margin-bottom: -2px;
border-radius: 4px;
}

mySlider::handle:horizontal:hover {
background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #fff, stop:1 #ddd);
border: 1px solid #444;
border-radius: 4px;
}

mySlider::sub-page:horizontal:disabled {
background: #bbb;
border-color: #999;
}

mySlider::add-page:horizontal:disabled {
background: #eee;
border-color: #999;
}

mySlider::handle:horizontal:disabled {
background: #eee;
border: 1px solid #aaa;
border-radius: 4px;
}
        """)


class MolecularModel(vtkActorCollection):
    r"""
    A collection of VTK Actors containing a representation of a molecular model. Always represented are the nuclei and connecting bonds; an optional additional Actor is a contour of an orbital or other data.
    """

    def __init__(self, source: dict | CubeData | str | list[str],
                 radius_scale: float = 0.4, bond_radius: float = .15,
                 bond_colour: tuple[float, float, float] = (1.0, 1.0, 1.0),
                 contour_value: float = .1,
                 contour_colours: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
                 contour_opacity: float = 0.7):
        """

        :param source:  Either a list of atoms represented as a dict with keys atomic_number, charge, xyz, the latter being a tuple of floats, or a CubeData object, or an xyz represented as a list of lines, or a string, or a path to an xyz file ending in .xyz.
        :param radius_scale: How much to scale the covalent radii of atoms for drawing their representative sphere.
        :param bond_radius: Radius of the cylinders representing bonds.
        :param contour_value:
        :param contour_colours:
        :param contour_opacity:
        """
        source_ = source
        if isinstance(source, str):
            source_ = xyz_to_atoms(source)
        if isinstance(source, Structure):
            source_ = source.atoms
        self.geometry = GeometryActorCollection(source_, radius_scale=radius_scale, bond_radius=bond_radius,
                                                bond_colour=bond_colour)
        for item in self.geometry:
            self.AddItem(item)

        if isinstance(source_, CubeData):
            contour_value = settings['contour_value']
            contour_opacity = settings['contour_opacity']
            self.contour = CubeActor(source, contour_value=contour_value, colours=contour_colours,
                                     opacity=contour_opacity)
            self.AddItem(self.contour)

    @property
    def contour_value(self):
        return self.contour.contour_value

    @contour_value.setter
    def contour_value(self, value):
        self.contour.contour_value = value

    @property
    def opacity(self):
        return self.contour.opacity

    @opacity.setter
    def opacity(self, value: float):
        self.contour.opacity = value

    def set_contour_opacity(self, opacity: float):
        self.contour.opacity = opacity

    def set_contour_value(self, value: float):
        self.contour.contour_value = value


class NucleiActor(vtkActor):
    def __init__(self, source: list[dict] | CubeData, atomic_number=None, radius_scale=.5, bond_radius=.1):
        vtkActor.__init__(self)
        self.radius_scale = radius_scale
        self.atomic_number = atomic_number
        self.set_source(source)

    def update_data(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.update_data(source.atoms)
            return
        filtered_xyz = [atom['xyz'] for atom in source
                        if self.atomic_number is None or atom['atomic_number'] == self.atomic_number]
        if hasattr(self, 'points') and self.points.GetNumberOfPoints() == len(filtered_xyz):
            # Same atom count for this element as before (the normal case during
            # vibrational-mode animation, where only positions change) -- move the
            # existing points in place rather than handing the glyph filter a brand new
            # input polydata (and forcing a full GPU re-upload) every frame.
            for i, xyz in enumerate(filtered_xyz):
                self.points.SetPoint(i, xyz)
            self.points.Modified()
        else:
            self.points = vtkPoints()
            for xyz in filtered_xyz:
                self.points.InsertNextPoint(xyz)
            polydata = vtkPolyData()
            polydata.SetPoints(self.points)
            self.glyph.SetInputData(polydata)
        self.glyph.Update()

    # Full resolution (~20000 triangles/sphere): used whenever not animating, including
    # for a static-structure image export, where quality matters and cost is paid once.
    STATIC_SPHERE_RESOLUTION = 100

    def set_source(self, source: list[dict] | CubeData):
        angstrom = 1.8897161646321
        # vtkGlyph3D fully regenerates its whole output mesh from scratch on every
        # Update() -- it has no notion of "only positions changed" -- so during
        # vibrational-mode animation, where every atom moves every frame, sphere
        # resolution directly sets the dominant per-frame cost (confirmed: ~5-10ms per
        # element per frame at resolution 100, vs ~0.2-0.4ms at resolution 20). Kept
        # high here by default; set_sphere_resolution() below drops it while animating
        # and restores it afterwards (see MoleculeDisplay._start/_stop_vibration_animation).
        self.sphere_source = vtkSphereSource(phi_resolution=self.STATIC_SPHERE_RESOLUTION,
                                             theta_resolution=self.STATIC_SPHERE_RESOLUTION)
        self.sphere_source.SetRadius(0.2)
        if self.atomic_number is not None:
            self.sphere_source.SetRadius(self.radius_scale * angstrom * covalent_radii[self.atomic_number])
        self.glyph = vtkGlyph3D()
        self.glyph.SetSourceConnection(self.sphere_source.GetOutputPort())
        mapper = vtkPolyDataMapper()
        self.update_data(source)
        mapper.SetInputConnection(self.glyph.GetOutputPort())
        self.SetMapper(mapper)
        self.GetProperty().SetColor(vtkNamedColors().GetColor3d('Salmon'))
        if self.atomic_number is not None:
            self.GetProperty().SetColor(colors.cpk_colors[self.atomic_number])
        self.SetOrigin(0.0, 0.0, 0.0)

    def set_sphere_resolution(self, resolution: int):
        self.sphere_source.SetPhiResolution(resolution)
        self.sphere_source.SetThetaResolution(resolution)


class NucleusLabelsActor(vtkActor2D):
    def __init__(self, source: list[dict] | CubeData, radius_scale=.5, bond_radius=.1):
        vtkActor2D.__init__(self)
        self.radius_scale = radius_scale
        self.set_source(source)

    def set_source(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.set_source(source.atoms)
            return
        polydata = atoms_to_polydata(source)
        labels = vtkStringArray(name='labels')
        labels.SetNumberOfValues(len(source))
        for i, atom in enumerate(source):
            labels.SetValue(i, periodic_table[atom['atomic_number'] - 1] + str(i + 1))
        polydata.GetPointData().AddArray(labels)
        sizes = vtkIntArray(name='sizes')
        sizes.SetNumberOfValues(len(source))
        for i, atom in enumerate(source):
            sizes.SetValue(i, 1)
        polydata.GetPointData().AddArray(sizes)
        point_set_to_label_hierarchy_filter = vtkPointSetToLabelHierarchy(
            label_array_name='labels',
            size_array_name='sizes',
        )
        point_set_to_label_hierarchy_filter.SetInputData(polydata)

        # Label colour needs to survive being drawn over any CPK sphere
        # colour (red, white, grey, and others -- but never a dark colour).
        # vtkLabelPlacementMapper takes its text colour from the
        # vtkTextProperty attached to the hierarchy filter, NOT from this
        # actor's own vtkProperty2D -- so a plain self.GetProperty().SetColor()
        # here (as previously attempted) has no visible effect and the text
        # always renders in VTK's default white. Instead, give the text
        # property a dark, semi-transparent background box behind black
        # text: since atom colours are never dark, this halo is legible
        # against any sphere colour without having to guess a single "safe"
        # foreground colour.
        text_property = vtkTextProperty()
        text_property.SetColor(0.0, 0.0, 0.0)
        text_property.SetBackgroundColor(1.0, 1.0, 1.0)
        text_property.SetBackgroundOpacity(0.75)
        text_property.SetBold(True)
        point_set_to_label_hierarchy_filter.SetTextProperty(text_property)

        mapper = vtkLabelPlacementMapper()
        mapper.SetInputConnection(point_set_to_label_hierarchy_filter.GetOutputPort())
        self.SetMapper(mapper)

    def update(self, source: list[dict] | CubeData):
        self.set_source(source)


def atoms_to_polydata(atoms: list[dict], atomic_number=None) -> vtkPolyData:
    points = vtkPoints()
    for i, atom in enumerate(atoms):
        if atomic_number is not None and atom['atomic_number'] != atomic_number:
            continue
        points.InsertNextPoint(atom['xyz'])
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    return polydata


class BondActorCollection(vtkActorCollection):
    def __init__(self, source: list[dict] | CubeData, bond_radius=.3, bond_colour=(1.0, 1.0, 1.0)):
        self.bond_colour = bond_colour
        self.bond_radius = bond_radius
        self.set_source(source)

    def set_source(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.set_source(source.atoms)
            return
        # Bonds are stored as atom indices, not the atom dicts themselves, so that
        # update() can move them to follow a new (distinct) list of atom coordinates
        # -- eg an animation frame -- while keeping the connectivity computed here.
        self.bonds = []
        self.atoms = source
        angstrom = 1.8897161646321
        for i, iatom in enumerate(self.atoms):
            for j, jatom in enumerate(self.atoms[:i]):
                distance = np.linalg.norm(np.array(iatom['xyz']) - np.array(jatom['xyz']))
                if 0.9 * distance / angstrom < covalent_radii[iatom['atomic_number']] + covalent_radii[
                    jatom['atomic_number']]:
                    actor = BondActor(iatom['xyz'], jatom['xyz'], radius=self.bond_radius, colour=self.bond_colour)
                    self.AddItem(actor)
                    self.bonds.append((i, j, actor))

    def update(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.update(source.atoms)
            return
        self.atoms = source
        for i, j, actor in self.bonds:
            actor.update(source[i]['xyz'], source[j]['xyz'])


class CubeActor(vtkActor):
    def __init__(self, cube_data: CubeData, contour_value: float = .05,
                 colours: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)], opacity: float = 0.7):
        vtkActor.__init__(self)
        self.SetMapper(vtkPolyDataMapper())
        self._contour_value = contour_value
        self.cube(cube_data)
        self.colours = colours
        self.opacity = opacity

    def cube(self, cube_data: CubeData):
        self.contour_filter = vtkContourFilter()
        self.contour_filter.SetInputData(create_vtk_image_data(cube_data))
        self.update_contour_value()
        self.SetOrigin(0.0, 0.0, 0.0)

    def update_contour_value(self):
        self.contour_filter.GenerateValues(2, [-self.contour_value, self.contour_value])
        self.contour_filter.Update()
        self.GetMapper().SetInputConnection(self.contour_filter.GetOutputPort())

    @property
    def opacity(self, value: float = None):
        if value is not None:
            self.GetProperty().SetOpacity(value)
        return self.GetProperty().GetOpacity()

    @opacity.setter
    def opacity(self, value: float):
        self.GetProperty().SetOpacity(value)

    @property
    def contour_value(self, value: float = None):
        if value is not None:
            self._contour_value = value
            self.update_contour_value()
        return self._contour_value

    @contour_value.setter
    def contour_value(self, value: float):
        self._contour_value = value
        self.update_contour_value()

    @property
    def colours(self, value: list[tuple[float, float, float]] = None):
        if value is not None:
            self._colours = value
            self.update_colours()
        return self._colours

    @colours.setter
    def colours(self, value: list[tuple[float, float, float]]):
        self._colours = value
        self.update_colours()

    def update_colours(self):
        color_tf = vtkColorTransferFunction()
        color_tf.AddRGBPoint(-0.000000001, *self.colours[0])
        if len(self.colours) > 1:
            color_tf.AddRGBPoint(0.000000001, *self.colours[1])
        self.GetMapper().SetLookupTable(color_tf)


def create_vtk_image_data(cube_data: CubeData) -> vtkImageData:
    vtk_image_data = vtkImageData()
    vtk_image_data.SetDimensions(*cube_data.dimensions)
    if np.any(cube_data.cells != np.diagflat(np.diagonal(cube_data.cells))):
        raise ValueError('Rotated or non-orthogonal cells not yet supported')
    vtk_image_data.SetSpacing(*np.diagonal(cube_data.cells))
    vtk_image_data.SetOrigin(*cube_data.origin)
    scalars = vtkFloatArray()
    scalars.SetName(cube_data.title[0])
    data = np.asfortranarray(cube_data.data)
    scalars.SetNumberOfValues(cube_data.data.size)
    i = 0
    for iz in range(cube_data.dimensions[2]):
        for iy in range(cube_data.dimensions[1]):
            for ix in range(cube_data.dimensions[0]):
                scalars.SetValue(i, data[ix, iy, iz])
                i += 1

    # for i, val in enumerate(data.flatten()):
    #     scalars.SetValue(i, val)
    vtk_image_data.GetPointData().SetScalars(scalars)
    return vtk_image_data


class GeometryActorCollection(vtkActorCollection):
    def __init__(self, source: dict | CubeData, atomic_number=None, radius_scale=.5, bond_radius=.1,
                 bond_colour=(1.0, 1.0, 1.0)):
        geom = source.atoms if isinstance(source, CubeData) else source
        assert isinstance(geom, list)
        vtkActorCollection.__init__(self)
        for atomic_number in {d['atomic_number'] for d in geom}:
            self.AddItem(NucleiActor(source, atomic_number=atomic_number, radius_scale=radius_scale))
        self.bond_actor_collection = BondActorCollection(source, bond_radius=bond_radius, bond_colour=bond_colour)
        for actor in self.bond_actor_collection:
            self.AddItem(actor)
        if False:
            geom2 = [d for d in geom]
            for d in geom2:
                d['xyz'] = [d['xyz'][i] * 1.5 for i in range(3)]
            self.update(geom2)

    def update(self, source: dict | CubeData):
        geom = source.atoms if isinstance(source, CubeData) else source
        for item in self:
            if isinstance(item, NucleiActor):
                item.update_data(geom)
        if hasattr(self, 'bond_actor_collection'):
            self.bond_actor_collection.update(geom)

    def set_sphere_resolution(self, resolution: int):
        for item in self:
            if isinstance(item, NucleiActor):
                item.set_sphere_resolution(resolution)


class BondActor(vtkActor):
    def __init__(self, startPoint: list[int], endPoint: list[int], radius: float = 1.0,
                 resolution: int = 30, colour=(1.0, 1.0, 1.0)):
        vtkActor.__init__(self)
        self.GetProperty().SetColor(colour)
        self.radius = radius
        self.resolution = resolution
        # A single unit cylinder (radius 1, height 1) is built once and reused for the
        # actor's lifetime; update() repositions/resizes it purely via the actor's own
        # vtkUserTransform, never touching the mesh. This matters for vibrational-mode
        # animation, where update() runs every frame: the previous approach rebuilt the
        # cylinder source, transform filter and mapper from scratch each call, forcing a
        # full geometry re-upload to the GPU per bond per frame -- the dominant cause of
        # animation jank. Moving the per-frame work to a small transform matrix update
        # instead is orders of magnitude cheaper.
        cylinder_source = vtkCylinderSource()
        cylinder_source.SetResolution(resolution)
        cylinder_source.SetRadius(1.0)
        cylinder_source.SetHeight(1.0)
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(cylinder_source.GetOutputPort())
        self.SetMapper(mapper)
        self.user_transform = vtkTransform()
        self.SetUserTransform(self.user_transform)
        self.update(startPoint, endPoint)

    def update(self, startPoint: list[int], endPoint: list[int]):
        set_bond_transform(self.user_transform, startPoint, endPoint, radius=self.radius)


def set_bond_transform(transform: vtkTransform, startPoint: list[int], endPoint: list[int], radius: float = 1.0):
    """
    Set `transform` (mutated in place) to place a unit cylinder (radius 1, height 1,
    centred on the origin, axis along Y) so that it joins startPoint to endPoint with
    the given radius. Adapted from
    https://examples.vtk.org/site/Python/GeometricObjects/OrientedCylinder, which built
    a fresh vtkPolyDataMapper for this each call; here the same maths instead updates an
    existing vtkTransform, so it can be called every animation frame cheaply.
    """
    # Compute a basis
    normalizedX = [0] * 3
    normalizedY = [0] * 3
    normalizedZ = [0] * 3

    # The X axis is a vector from start to end
    vtkMath.Subtract(endPoint, startPoint, normalizedX)
    length = vtkMath.Norm(normalizedX)
    vtkMath.Normalize(normalizedX)

    # The Z axis is an arbitrary vector cross X
    arbitrary = [0] * 3
    rng = vtkMinimalStandardRandomSequence()
    rng.SetSeed(8775070)  # For testing.
    for i in range(0, 3):
        rng.Next()
        arbitrary[i] = rng.GetRangeValue(-10, 10)
    vtkMath.Cross(normalizedX, arbitrary, normalizedZ)
    vtkMath.Normalize(normalizedZ)

    # The Y axis is Z cross X
    vtkMath.Cross(normalizedZ, normalizedX, normalizedY)
    matrix = vtkMatrix4x4()

    # Create the direction cosine matrix
    matrix.Identity()
    for i in range(0, 3):
        matrix.SetElement(i, 0, normalizedX[i])
        matrix.SetElement(i, 1, normalizedY[i])
        matrix.SetElement(i, 2, normalizedZ[i])

    # Apply the transforms
    transform.Identity()
    transform.Translate(startPoint)  # translate to starting point
    transform.Concatenate(matrix)  # apply direction cosines
    transform.RotateZ(-90.0)  # align cylinder to x axis
    transform.Scale(radius, length, radius)  # scale to bond radius and length
    transform.Translate(0, .5, 0)  # translate to start of cylinder


def xyz_to_atoms(xyz: str | list[str]):
    angstrom = 1.8897161646321
    if isinstance(xyz, str) and xyz.endswith('.xyz'):
        try:
            with open(xyz, 'r') as f:
                return xyz_to_atoms(f.readlines())
        except:
            pass
    if isinstance(xyz, str):
        return xyz_to_atoms(xyz.splitlines())
    assert isinstance(xyz, list)
    atoms = []
    for line in xyz[2:]:
        line = line.strip().split()
        element = line[0]
        atomic_number = chemical_symbols.index(element) + 0
        atoms.append({'atomic_number': atomic_number, 'charge': atomic_number,
                      'xyz': tuple([float(line[k + 1]) * angstrom for k in range(3)])})
    return atoms
