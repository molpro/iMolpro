import os

import math
# import vtk
import numpy as np
from pymolpro import Orbital

from .project import Structure

try:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
        QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
    from PySide6.QtCore import Qt, QSize
except ImportError:
    try:
        from PyQt6.QtGui import QColor, QPalette
        from PyQt6.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
            QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
        from PyQt6.QtCore import Qt, QSize
    except ImportError:
        from PyQt5.QtGui import QColor, QPalette
        from PyQt5.QtWidgets import QFileDialog, QPushButton, QColorDialog, QWidget, QLabel, QGridLayout, QHBoxLayout, \
            QVBoxLayout, QSlider, QSizePolicy, QComboBox, QLayout, QCheckBox, QToolButton
        from PyQt5.QtCore import Qt, QSize

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
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from enum import Enum

from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkFiltersSources import vtkSphereSource, vtkCylinderSource
from vtkmodules.vtkIOExportGL2PS import vtkGL2PSExporter
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingAnnotation import vtkCubeAxesActor
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkLightKit, vtkActor2D, vtkActorCollection, vtkPolyDataMapper, \
    vtkColorTransferFunction
from vtkmodules.vtkRenderingLabel import vtkPointSetToLabelHierarchy, vtkLabelPlacementMapper


class ColourScheme(Enum):
    # dark = 20, 20, 30,
    dark = 0, 4, 0x35,
    light = 236, 236, 236,
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
                 ):
        QWidget.__init__(self, parent)
        self.background_colour = background_colour.value if isinstance(background_colour,
                                                                       ColourScheme) else background_colour
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
                 contour_value=.05, contour_opacity=.7,
                 resolution: float = .5,
                 metadata: dict = {},
                 ):
        if background_colour is None:
            rgb = parent.palette().color(QPalette.Window).rgb()
            background_colour = (((rgb >> 16) & 0xFF), ((rgb >> 8) & 0xFF), (rgb & 0xFF))
        QWidget.__init__(self, parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.parent = parent

        if isinstance(source, list) and len(source) > 0 and isinstance(source[-1], dict):
            data = source
        elif isinstance(source, Structure):
            data = source
            if source.vibrations:
                metadata['vibrations'] = source.vibrations
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
                                              contour_opacity=contour_opacity)
        layout.addWidget(self.molecule_widget)

        self.right_panel = ControlPanel(self, metadata=metadata)
        layout.addWidget(self.right_panel)

    def get_cube(self, contour_value=None):
        # print('get_cube',self.orbital.ID,self.resolution,contour_value,'')
        key = self.orbital, self.resolution, contour_value
        if key not in self.cubes:
            # print('get_cube',self.orbital.ID,self.resolution,contour_value,'creating')
            self.cubes[key] = self.orbital.cube_data(resolution=self.resolution, threshold=contour_value * .1)
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

    def set_vibration(self, mode_id):
        self.vibrational_mode = mode_id
        self.right_panel.refresh()

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

    def __init__(self, source, parent=None, axes: bool = False,
                 background_colour: tuple | ColourScheme = ColourScheme.dark,
                 contour_value=.05, contour_opacity=.7,
                 sliders: bool = True,
                 ):
        StyledWidget.__init__(self, parent, background_colour=background_colour)

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
        self.scene.GetRenderWindow().GetInteractor().Render()

    @property
    def contour_value(self):
        return self.model.contour_value

    def set_contour_value(self, value):
        contour_value = self.contour_slider_minimum * math.exp(
            value * 0.01 * math.log(self.contour_slider_maximum / self.contour_slider_minimum))
        self.model.set_contour_value(contour_value)
        self.scene.GetRenderWindow().GetInteractor().Render()

    def set_background_colour(self, colour: QColor | int | tuple[float, float, float]):
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
            return self.set_background_colour((red, green, blue))
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

        if 'vibrations' in metadata:
            vibration_selector = QComboBox()
            for i, mode in enumerate(metadata['vibrations'].modes):
                vibration_selector.addItem(f'{i + 1}: {mode["wavenumber"]} cm-1')
            # vibration_selector.currentIndexChanged.connect(self.parent.molecule_widget.model.set_vibration)
            self.control_layout.add('Normal mode', vibration_selector)
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
                    self.parent.molecule_widget.model.contour_value / self.contour_slider_minimum) / math.log(
                    self.contour_slider_maximum / self.contour_slider_minimum)))
            self.control_layout.add('Contour value', contour_slider)

            opacity_slider = mySlider(self)
            opacity_slider.valueChanged.connect(self.parent.molecule_widget.set_contour_opacity)
            opacity_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
            opacity_slider.setValue(int(self.parent.molecule_widget.model.contour.opacity * 100))
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
        for i, name in enumerate(['dark', 'black', 'white', 'light']):
            # print('ColourScheme', name, ': ', ColourScheme[name].value)
            # button = QPushButton('')
            button = QToolButton(self)
            button.setMaximumSize(QSize(15, 15))
            button.setStyleSheet(f'background-color: rgb{str(ColourScheme[name].value)}; border:none;')
            colour_selection_layout2.addWidget(button)
            button.clicked.connect(
                lambda checked, name=name: self.parent.molecule_widget.set_background_colour(ColourScheme[name].value))
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
        QVTKRenderWindowInteractor.__init__(self)  # , parent)
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
        pdf_exporter.Write()


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
                 radius_scale: float = 0.6, bond_radius: float = .25,
                 bond_colour: tuple[float, float, float] = (1.0, 1.0, 1.0),
                 contour_value: float = .05,
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
        polydata = atoms_to_polydata(source, self.atomic_number)
        self.glyph.SetInputData(polydata)
        self.glyph.Update()

    def set_source(self, source: list[dict] | CubeData):
        angstrom = 1.8897161646321
        sphere_source = vtkSphereSource(phi_resolution=50, theta_resolution=50)
        sphere_source.SetRadius(0.2)
        if self.atomic_number is not None:
            sphere_source.SetRadius(self.radius_scale * angstrom * covalent_radii[self.atomic_number])
        self.glyph = vtkGlyph3D()
        self.glyph.SetSourceConnection(sphere_source.GetOutputPort())
        mapper = vtkPolyDataMapper()
        self.update_data(source)
        mapper.SetInputConnection(self.glyph.GetOutputPort())
        self.SetMapper(mapper)
        self.GetProperty().SetColor(vtkNamedColors().GetColor3d('Salmon'))
        if self.atomic_number is not None:
            self.GetProperty().SetColor(colors.cpk_colors[self.atomic_number])
        self.SetOrigin(0.0, 0.0, 0.0)
        # self.GetProperty().SetOpacity(.1)


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
        mapper = vtkLabelPlacementMapper()
        mapper.SetInputConnection(point_set_to_label_hierarchy_filter.GetOutputPort())
        self.SetMapper(mapper)
        self.GetProperty().SetColor(vtkNamedColors().GetColor3d('Salmon'))
        # self.GetProperty().SetOpacity(.1)


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
        self.bonds=[]
        self.atoms = source
        angstrom = 1.8897161646321
        for i, iatom in enumerate(self.atoms):
            for j, jatom in enumerate(self.atoms[:i]):
                distance = np.linalg.norm(np.array(iatom['xyz']) - np.array(jatom['xyz']))
                if 0.9 * distance / angstrom < covalent_radii[iatom['atomic_number']] + covalent_radii[
                    jatom['atomic_number']]:
                    actor = BondActor(iatom['xyz'], jatom['xyz'], radius=self.bond_radius, colour=self.bond_colour)
                    self.AddItem(actor)
                    self.bonds.append((iatom, jatom, actor))

    def update(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.update(source.atoms)
            return
        for bond in self.bonds:
            bond[2].update(bond[0]['xyz'], bond[1]['xyz'])


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
                d['xyz'] = [d['xyz'][i]*1.5 for i in range(3)]
            self.update(geom2)

    def update(self, source: dict | CubeData):
        geom = source.atoms if isinstance(source, CubeData) else source
        for item in self:
            if isinstance(item, NucleiActor):
                item.update(geom)
        if hasattr(self, 'bond_actor_collection'):
            self.bond_actor_collection.update(geom)


class BondActor(vtkActor):
    def __init__(self, startPoint: list[int], endPoint: list[int], radius: float = 1.0,
                               resolution: int = 15, colour=(1.0, 1.0, 1.0)):
        self.GetProperty().SetColor(colour)
        self.radius = radius
        self.resolution = resolution
        self.update(startPoint, endPoint)


    def update(self, startPoint: list[int], endPoint: list[int]):
        self.SetMapper(join_points_with_cylinder(startPoint, endPoint, radius=self.radius, resolution=self.resolution))

def join_points_with_cylinder(startPoint: list[int], endPoint: list[int], radius: float = 1.0,
                              resolution: int = 15) -> vtkPolyDataMapper:
    """
    From https://examples.vtk.org/site/Python/GeometricObjects/OrientedCylinder

    :param startPoint:
    :param endPoint:
    :param radius:
    :param resolution:
    :return:
    """
    cylinderSource = vtkCylinderSource()
    cylinderSource.SetResolution(resolution)
    cylinderSource.SetRadius(radius)
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
    transform = vtkTransform()
    transform.Translate(startPoint)  # translate to starting point
    transform.Concatenate(matrix)  # apply direction cosines
    transform.RotateZ(-90.0)  # align cylinder to x axis
    transform.Scale(1.0, length, 1.0)  # scale along the height vector
    transform.Translate(0, .5, 0)  # translate to start of cylinder

    # Transform the polydata
    transformPD = vtkTransformPolyDataFilter()
    transformPD.SetTransform(transform)
    transformPD.SetInputConnection(cylinderSource.GetOutputPort())

    # Create a mapper and actor for the arrow
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(transformPD.GetOutputPort())
    return mapper


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
