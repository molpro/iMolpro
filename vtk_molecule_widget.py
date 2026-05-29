from PyQt5 import Qt, QtCore
import math
import vtk
import numpy as np
from jupyter_client.kernelspec import find_kernel_specs
from numpy.ma.core import right_shift
from prompt_toolkit.key_binding.bindings.named_commands import self_insert
from pymolpro.cube_data import CubeData
from ase.data import colors, covalent_radii, chemical_symbols
from vtkmodules.vtkFiltersCore import vtkGlyph3D
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from enum import Enum


class ColourScheme(Enum):
    dark = 20, 20, 30,
    light = 255, 255, 255,
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


class StyledWidget(Qt.QWidget):
    def __init__(self, parent=None, background_colour: tuple | ColourScheme = ColourScheme.dark,
                 ):
        Qt.QWidget.__init__(self, parent)
        self.background_colour = background_colour.value if isinstance(background_colour,
                                                                       ColourScheme) else background_colour
        self.dark = sum(self.background_colour) / 3.0 < 128
        self.dark = (self.background_colour[0] * 0.299 + self.background_colour[1] * 0.587 + self.background_colour[
            2] * 0.114) / 255.0 < 0.5
        palette = Qt.QPalette()
        palette.setColor(Qt.QPalette.Window, Qt.QColor(*self.background_colour))
        self.setAutoFillBackground(True)
        self.setPalette(palette)
        if self.dark:
            self.setStyleSheet("* { color: rgb(255,255,255); font-size: 10px }\n")
        else:
            self.setStyleSheet("* { color: rgb(0,0,0); font-size: 10px }\n")


class FixedLabel(Qt.QLabel):
    def __init__(self, text, parent=None):
        Qt.QLabel.__init__(self, text, parent)
        self.setSizePolicy(Qt.QSizePolicy.Fixed, Qt.QSizePolicy.Fixed)


class ItemLayout(Qt.QGridLayout):
    def __init__(self, parent=None):
        Qt.QGridLayout.__init__(self, parent)
        self.setContentsMargins(0, 0, 0, 0)
        # self.setSpacing(0)
        self.row = 0

    def add(self, title, content):
        self.addWidget(FixedLabel(title + ':'), self.row, 0)
        if isinstance(content, Qt.QWidget):
            self.addWidget(content, self.row, 1)
        elif isinstance(content, Qt.QLayout):
            self.addLayout(content, self.row, 1, )
        self.row += 1
        return self.row-1


class OrbitalsWidget(Qt.QWidget):
    def get_cube(self, contour_value=None):
        # print('get_cube',self.orbital.ID,self.resolution,contour_value,'')
        key = self.orbital, self.resolution, contour_value
        if key not in self.cubes:
            # print('get_cube',self.orbital.ID,self.resolution,contour_value,'creating')
            self.cubes[key] = self.orbital.cube_data(resolution=self.resolution, threshold=contour_value * .1)
        return self.cubes[key]

    def __init__(self, orbitals: list, parent=None, axes: bool = False,
                 background_colour: tuple | ColourScheme = ColourScheme.dark,
                 contour_value=.05, contour_opacity=.7,
                 resolution: float = .5,
                 ):
        # print('OrbitalsWidget', orbitals)
        Qt.QWidget.__init__(self, parent)
        layout = Qt.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.cubes = {}
        self.orbitals = orbitals
        self.resolution = resolution
        self.orbital = orbitals[-1]
        cube_data = self.get_cube(contour_value=contour_value)
        self.orbital_display = MoleculeWidget(cube_data, self, sliders=False, contour_value=contour_value,
                                              contour_opacity=contour_opacity)
        layout.addWidget(self.orbital_display)

        if True:
            self.right_panel = ControlPanel(self)
            layout.addWidget(self.right_panel)
        else: #legacy kept till working
            right_panel = Qt.QWidget()
            # layout.addWidget(right_panel)
            right_panel.setContentsMargins(0, 0, 0, 0)
            right_panel.setSizePolicy(Qt.QSizePolicy.Fixed, Qt.QSizePolicy.Preferred)
            right_layout = Qt.QVBoxLayout()
            right_panel.setLayout(right_layout)
            # layout.addLayout(right_layout)

            # test
            if False:
                index = layout.indexOf(right_panel)
                print('index',index)
                print('right_panel',right_panel)
                print(layout.itemAt(index).widget())
                layout.removeWidget(layout.itemAt(index).widget())
                layout.addWidget(right_panel)
            #end test

            control_layout = ItemLayout()
            right_layout.addLayout(control_layout)
            right_layout.addStretch()
            # control_layout.addWidget(Qt.QLabel('Orbitals'),0,0)

            orbital_selector = Qt.QComboBox()
            for orbital in orbitals[::-1]:
                orbital_selector.addItem(str(orbital.ID))
            orbital_selector.currentTextChanged.connect(self.set_orbital)
            # orbital_selector.setBackgroundColor(Qt.QColor(*self.background_colour))
            # palette = self.palette()
            # palette.setColor(Qt.QPalette.Base, Qt.QColor(*self.background_colour))
            # palette.setColor(Qt.QPalette.Base, Qt.QColor('Red'))
            # orbital_selector.setPalette(palette)
            # orbital_selector.setAutoFillBackground(True)
            orbital_selector.setMinimumWidth(orbital_selector.minimumSizeHint().width())
            control_layout.add('Orbital', orbital_selector)

            if hasattr(self.orbital, 'occupation'):
                self.occupation_row = control_layout.add('Occupation', Qt.QLabel(str(self.orbital.occupation)))

            if hasattr(self.orbital, 'energy'):
                self.energy_row = control_layout.add('Energy', Qt.QLabel(str(self.orbital.energy)))

            # control_layout.addWidget(FixedLabel('Contour:'), row, 0)
            contour_slider = mySlider(self)
            self.contour_slider_minimum = 0.003
            self.contour_slider_maximum = 0.5
            contour_slider.valueChanged.connect(self.orbital_display.set_contour_value)
            contour_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
            contour_slider.setValue(
                int(100 * math.log(self.orbital_display.model.contour_value / self.contour_slider_minimum) / math.log(
                    self.contour_slider_maximum / self.contour_slider_minimum)))
            control_layout.add('Contour value', contour_slider)

            opacity_slider = mySlider(self)
            opacity_slider.valueChanged.connect(self.orbital_display.set_contour_opacity)
            opacity_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
            opacity_slider.setValue(int(self.orbital_display.model.contour.opacity * 100))
            control_layout.add('Opacity', opacity_slider)

            if False:
                resolution_slider = mySlider(self)
                resolution_slider.valueChanged.connect(self.set_resolution)
                resolution_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
                resolution_slider.setValue(int(self.resolution * 100))
                resolution_label = FixedLabel('Resolution:')
                control_layout.addWidget(resolution_label, row, 0)
                control_layout.addWidget(resolution_slider, row, 1)
                row += 1

            resolution_label = FixedLabel('Resolution:')
            resolution_layout = Qt.QHBoxLayout()
            # resolution_layout.setContentsMargins(0,0,0,0)
            # resolution_layout.setSpacing(0)
            coarser_button = Qt.QPushButton('-')
            resolution_layout.addWidget(coarser_button)
            coarser_button.clicked.connect(lambda: self.set_resolution('-'))
            finer_button = Qt.QPushButton('+')
            resolution_layout.addWidget(finer_button)
            finer_button.clicked.connect(lambda: self.set_resolution('+'))
            control_layout.add('Resolution', resolution_layout)

            atom_labels_checkbox = Qt.QCheckBox()
            control_layout.add('Atom labels', atom_labels_checkbox)
            atom_labels_checkbox.clicked.connect(lambda: self.set_atom_labels(atom_labels_checkbox.isChecked()))

            control_layout.add('Background colour', FixedLabel('To Do'))

            control_layout.add('Export image', FixedLabel('To Do'))

            # control_layout.addStretch()

    def set_atom_labels(self, atom_labels: bool):
        pass  # TODO implement

    def set_orbital(self, orbital_id):
        # print('set_orbital', orbital_id)
        self.orbital = self.orbitals[[orbital.ID for orbital in self.orbitals].index(orbital_id)]
        cube_data = self.get_cube(self.orbital_display.model.contour_value)
        # print(str(cube_data)[:100] + '...')
        self.right_panel.refresh()
        self.orbital_display.refresh_model(cube_data)
        pass

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

    def __init__(self, source, parent=None, axes: bool = False,
                 background_colour: tuple | ColourScheme = ColourScheme.dark,
                 contour_value=.05, contour_opacity=.7,
                 sliders: bool = True,
                 ):
        StyledWidget.__init__(self, parent, background_colour=background_colour)

        layout = Qt.QVBoxLayout()
        self.setLayout(layout)
        self.scene = MoleculeScene(self)
        self.model = MolecularModel(source, contour_value=contour_value, contour_opacity=contour_opacity,
                                    bond_colour=(0.8, 0.8, 0.8) if self.dark else (0.6, 0.6, 0.6))
        self.scene.Add(self.model)
        self.scene.SetBackground(*[c / 255.0 for c in self.background_colour])
        if axes:
            self.add_axes(self.scene)

        layout.addWidget(self.scene)

        self.contour_slider_minimum = 0.003
        self.contour_slider_maximum = 0.5
        if sliders and hasattr(self.model, 'contour'):
            slider_layout = Qt.QGridLayout()
            slider_layout.addWidget(Qt.QLabel('Contour:'), 0, 0)
            layout.addLayout(slider_layout)
            opacity_slider = mySlider(self)
            opacity_slider.valueChanged.connect(self.set_contour_opacity)
            opacity_slider.setValue(int(self.model.contour.opacity * 100))
            slider_layout.addWidget(Qt.QLabel('Opacity'), 0, 1)
            slider_layout.addWidget(opacity_slider, 0, 2)

            contour_slider = mySlider(self)
            contour_slider.valueChanged.connect(self.set_contour_value)
            contour_slider.setValue(
                int(100 * math.log(self.model.contour_value / self.contour_slider_minimum) / math.log(
                    self.contour_slider_maximum / self.contour_slider_minimum)))
            slider_layout.addWidget(Qt.QLabel('Value'), 0, 3)
            slider_layout.addWidget(contour_slider, 0, 4)

        self.show()

        self.scene.Start()

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

    def add_axes(self, scene: MoleculeScene):
        axes = vtk.vtkCubeAxesActor()

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

class ControlPanel(Qt.QWidget):
    def __init__(self, parent):
        # print('ControlPanel __init__')
        super().__init__(parent)
        self.parent = parent
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(Qt.QSizePolicy.Fixed, Qt.QSizePolicy.Preferred)
        self.layout = Qt.QVBoxLayout()
        self.setLayout(self.layout)
        self.setup()
        self.refresh()

    def refresh(self):
        if hasattr(self,'energy_widget'):
            if hasattr(self.parent.orbital,'energy') :
                self.energy_widget.setText(str(self.parent.orbital.energy))
            else:
                self.energy_widget.setText('None')
        if hasattr(self,'occupation_widget'):
            if hasattr(self.parent.orbital,'occupation') :
                self.occupation_widget.setText(str(self.parent.orbital.occupation))
            else:
                self.occupation_widget.setText('None')
        pass

    def setup(self):

        while w:= self.findChild(Qt.QWidget):
            w.setParent(None)

        self.control_layout = ItemLayout()
        self.layout.addLayout(self.control_layout)
        self.layout.addStretch()
        # self.control_layout.addWidget(Qt.QLabel('Orbitals'),0,0)

        orbital_selector = Qt.QComboBox()
        for orbital in self.parent.orbitals[::-1]:
            orbital_selector.addItem(str(orbital.ID))
        orbital_selector.currentTextChanged.connect(self.parent.set_orbital)
        # orbital_selector.setBackgroundColor(Qt.QColor(*self.background_colour))
        # palette = self.palette()
        # palette.setColor(Qt.QPalette.Base, Qt.QColor(*self.background_colour))
        # palette.setColor(Qt.QPalette.Base, Qt.QColor('Red'))
        # orbital_selector.setPalette(palette)
        # orbital_selector.setAutoFillBackground(True)
        orbital_selector.setMinimumWidth(orbital_selector.minimumSizeHint().width())
        self.control_layout.add('Orbital', orbital_selector)


        if hasattr(self.parent.orbital, 'occupation'):
            row = self.control_layout.add('Occupation', Qt.QLabel(str(self.parent.orbital.occupation)))
            self.occupation_widget = self.control_layout.itemAtPosition(row, 1).widget()

        if hasattr(self.parent.orbital, 'energy'):
            row = self.control_layout.add('Energy', Qt.QLabel(str(self.parent.orbital.energy)))
            self.energy_widget = self.control_layout.itemAtPosition(row, 1).widget()

        # self.control_layout.addWidget(FixedLabel('Contour:'), row, 0)
        contour_slider = mySlider(self)
        self.contour_slider_minimum = 0.003
        self.contour_slider_maximum = 0.5
        contour_slider.valueChanged.connect(self.parent.orbital_display.set_contour_value)
        contour_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
        contour_slider.setValue(
            int(100 * math.log(self.parent.orbital_display.model.contour_value / self.contour_slider_minimum) / math.log(
                self.contour_slider_maximum / self.contour_slider_minimum)))
        self.control_layout.add('Contour value', contour_slider)

        opacity_slider = mySlider(self)
        opacity_slider.valueChanged.connect(self.parent.orbital_display.set_contour_opacity)
        opacity_slider.setMaximumWidth(orbital_selector.minimumSizeHint().width())
        opacity_slider.setValue(int(self.parent.orbital_display.model.contour.opacity * 100))
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
        resolution_layout = Qt.QHBoxLayout()
        # resolution_layout.setContentsMargins(0,0,0,0)
        # resolution_layout.setSpacing(0)
        coarser_button = Qt.QPushButton('-')
        resolution_layout.addWidget(coarser_button)
        coarser_button.clicked.connect(lambda: self.parent.set_resolution('-'))
        finer_button = Qt.QPushButton('+')
        resolution_layout.addWidget(finer_button)
        finer_button.clicked.connect(lambda: self.parent.set_resolution('+'))
        self.control_layout.add('Resolution', resolution_layout)

        atom_labels_checkbox = Qt.QCheckBox()
        self.control_layout.add('Atom labels', atom_labels_checkbox)
        atom_labels_checkbox.clicked.connect(lambda: self.parent.set_atom_labels(atom_labels_checkbox.isChecked()))

        self.control_layout.add('Background colour', FixedLabel('To Do'))

        self.control_layout.add('Export image', FixedLabel('To Do'))

        # self.control_layout.addStretch()

class MoleculeScene(QVTKRenderWindowInteractor):

    def __init__(self, parent=None):
        QVTKRenderWindowInteractor.__init__(self)  # , parent)
        self.renderer = vtk.vtkRenderer()
        self.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.GetRenderWindow().GetInteractor()
        self.interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.GetRenderWindow().GetInteractor().Initialize()

    def Add(self, source):
        if isinstance(source, vtk.vtkActor):
            self.renderer.AddActor(source)
        elif isinstance(source, vtk.vtkActorCollection):
            for actor in source:
                self.renderer.AddActor(actor)

    def Remove(self, source: vtk.vtkActor):
        self.renderer.RemoveActor(source)

    def SetBackground(self, r, g, b):
        self.renderer.SetBackground(r, g, b)

    def Start(self):
        self.renderer.ResetCamera()
        self.GetRenderWindow().GetInteractor().Initialize()
        self.GetRenderWindow().GetInteractor().Start()


class mySlider(Qt.QSlider):
    def __init__(self, parent=None):
        Qt.QSlider.__init__(self, parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setOrientation(QtCore.Qt.Horizontal)
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


class MolecularModel(vtk.vtkActorCollection):
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


class NucleiActor(vtk.vtkActor):
    def __init__(self, source: list[dict] | CubeData, atomic_number=None, radius_scale=.5, bond_radius=.1):
        vtk.vtkActor.__init__(self)
        self.radius_scale = radius_scale
        self.set_source(source, atomic_number=atomic_number)

    def set_source(self, source: list[dict] | CubeData, atomic_number=None):
        if isinstance(source, CubeData):
            self.set_source(source.atoms, atomic_number=atomic_number)
            return
        self.atoms = source
        points = vtk.vtkPoints()
        angstrom = 1.8897161646321
        for i, atom in enumerate(self.atoms):
            if atomic_number is not None and atom['atomic_number'] != atomic_number:
                continue
            points.InsertNextPoint(atom['xyz'])
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        # _colours=[colors.cpk_colors[atom['atomic_number']] for atom in self.atoms]
        sphere_source = vtk.vtkSphereSource(phi_resolution=50, theta_resolution=50)
        sphere_source.SetRadius(0.3)
        if atomic_number is not None:
            sphere_source.SetRadius(self.radius_scale * angstrom * covalent_radii[atomic_number])
        glyph = vtkGlyph3D()
        glyph.SetSourceConnection(sphere_source.GetOutputPort())
        glyph.SetInputData(polydata)
        glyph.Update()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(glyph.GetOutputPort())
        self.SetMapper(mapper)
        self.GetProperty().SetColor(vtk.vtkNamedColors().GetColor3d('Salmon'))
        if atomic_number is not None:
            self.GetProperty().SetColor(colors.cpk_colors[atomic_number])
        self.SetOrigin(0.0, 0.0, 0.0)
        # self.GetProperty().SetOpacity(.1)


class BondActorCollection(vtk.vtkActorCollection):
    def __init__(self, source: list[dict] | CubeData, bond_radius=.3, bond_colour=(1.0, 1.0, 1.0)):
        self.bond_colour = bond_colour
        self.bond_radius = bond_radius
        self.set_source(source)

    def set_source(self, source: list[dict] | CubeData):
        if isinstance(source, CubeData):
            self.set_source(source.atoms)
            return
        self.atoms = source
        angstrom = 1.8897161646321
        for i, iatom in enumerate(self.atoms):
            for j, jatom in enumerate(self.atoms[:i]):
                distance = np.linalg.norm(np.array(iatom['xyz']) - np.array(jatom['xyz']))
                if 0.9 * distance / angstrom < covalent_radii[iatom['atomic_number']] + covalent_radii[
                    jatom['atomic_number']]:
                    self.AddItem(join_points_with_cylinder(iatom['xyz'], jatom['xyz'], radius=self.bond_radius,
                                                           colour=self.bond_colour))


class CubeActor(vtk.vtkActor):
    def __init__(self, cube_data: CubeData, contour_value: float = .05,
                 colours: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)], opacity: float = 0.7):
        vtk.vtkActor.__init__(self)
        self.SetMapper(vtk.vtkPolyDataMapper())
        self._contour_value = contour_value
        self.cube(cube_data)
        self.colours = colours
        self.opacity = opacity

    def cube(self, cube_data: CubeData):
        self.contour_filter = vtk.vtkContourFilter()
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
        color_tf = vtk.vtkColorTransferFunction()
        color_tf.AddRGBPoint(-0.000000001, *self.colours[0])
        if len(self.colours) > 1:
            color_tf.AddRGBPoint(0.000000001, *self.colours[1])
        self.GetMapper().SetLookupTable(color_tf)


def create_vtk_image_data(cube_data: CubeData) -> vtk.vtkImageData:
    vtk_image_data = vtk.vtkImageData()
    vtk_image_data.SetDimensions(*cube_data.dimensions)
    if np.any(cube_data.cells != np.diagflat(np.diagonal(cube_data.cells))):
        raise ValueError('Rotated or non-orthogonal cells not yet supported')
    vtk_image_data.SetSpacing(*np.diagonal(cube_data.cells))
    vtk_image_data.SetOrigin(*cube_data.origin)
    scalars = vtk.vtkFloatArray()
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


class GeometryActorCollection(vtk.vtkActorCollection):
    def __init__(self, source: dict | CubeData, atomic_number=None, radius_scale=.5, bond_radius=.1,
                 bond_colour=(1.0, 1.0, 1.0)):
        geom = source.atoms if isinstance(source, CubeData) else source
        assert isinstance(geom, list)
        vtk.vtkActorCollection.__init__(self)
        for atomic_number in {d['atomic_number'] for d in geom}:
            self.AddItem(NucleiActor(source, atomic_number=atomic_number, radius_scale=radius_scale))
        for actor in BondActorCollection(source, bond_radius=bond_radius, bond_colour=bond_colour):
            self.AddItem(actor)


def join_points_with_cylinder(startPoint: list[int], endPoint: list[int], radius: float = 1.0,
                              resolution: int = 15, colour=(1.0, 1.0, 1.0)) -> vtkActor:
    """
    From https://examples.vtk.org/site/Python/GeometricObjects/OrientedCylinder

    :param startPoint:
    :param endPoint:
    :param radius:
    :param resolution:
    :return:
    """
    cylinderSource = vtk.vtkCylinderSource()
    cylinderSource.SetResolution(resolution)
    cylinderSource.SetRadius(radius)
    # Compute a basis
    normalizedX = [0] * 3
    normalizedY = [0] * 3
    normalizedZ = [0] * 3

    # The X axis is a vector from start to end
    vtk.vtkMath.Subtract(endPoint, startPoint, normalizedX)
    length = vtk.vtkMath.Norm(normalizedX)
    vtk.vtkMath.Normalize(normalizedX)

    # The Z axis is an arbitrary vector cross X
    arbitrary = [0] * 3
    rng = vtk.vtkMinimalStandardRandomSequence()
    rng.SetSeed(8775070)  # For testing.
    for i in range(0, 3):
        rng.Next()
        arbitrary[i] = rng.GetRangeValue(-10, 10)
    vtk.vtkMath.Cross(normalizedX, arbitrary, normalizedZ)
    vtk.vtkMath.Normalize(normalizedZ)

    # The Y axis is Z cross X
    vtk.vtkMath.Cross(normalizedZ, normalizedX, normalizedY)
    matrix = vtk.vtkMatrix4x4()

    # Create the direction cosine matrix
    matrix.Identity()
    for i in range(0, 3):
        matrix.SetElement(i, 0, normalizedX[i])
        matrix.SetElement(i, 1, normalizedY[i])
        matrix.SetElement(i, 2, normalizedZ[i])

    # Apply the transforms
    transform = vtk.vtkTransform()
    transform.Translate(startPoint)  # translate to starting point
    transform.Concatenate(matrix)  # apply direction cosines
    transform.RotateZ(-90.0)  # align cylinder to x axis
    transform.Scale(1.0, length, 1.0)  # scale along the height vector
    transform.Translate(0, .5, 0)  # translate to start of cylinder

    # Transform the polydata
    transformPD = vtk.vtkTransformPolyDataFilter()
    transformPD.SetTransform(transform)
    transformPD.SetInputConnection(cylinderSource.GetOutputPort())

    # Create a mapper and actor for the arrow
    mapper = vtk.vtkPolyDataMapper()
    actor = vtk.vtkActor()
    mapper.SetInputConnection(transformPD.GetOutputPort())

    actor.GetProperty().SetColor(colour)
    actor.SetMapper(mapper)
    return actor


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
