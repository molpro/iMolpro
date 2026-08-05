import copy
import re

import pymolpro
from pymolpro import molpro_input

try:
    from PySide6.QtCore import Signal as pyqtSignal, Qt, QSize
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QGridLayout, QCheckBox, \
        QToolButton, QPushButton
except ImportError:
    try:
        from PyQt6.QtCore import pyqtSignal, Qt, QSize
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QGridLayout, QCheckBox, \
            QToolButton, QPushButton
    except ImportError:
        from PyQt5.QtCore import pyqtSignal, Qt, QSize
        from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QGridLayout, QCheckBox, \
            QToolButton, QPushButton

try:
    UpArrow = Qt.ArrowType.UpArrow
    DownArrow = Qt.ArrowType.DownArrow
    CheckState = Qt.CheckState
    MatchFlag = Qt.MatchFlag
except:
    UpArrow = Qt.UpArrow
    DownArrow = Qt.DownArrow
    CheckState = Qt
    MatchFlag = Qt

from .BasisSelector import BasisSelector
from .SpinComboBox import SpinComboBox
from .CheckableComboBox import CheckableComboBox
from .OptionsDialog import OptionsDialog

import logging

logger = logging.getLogger(__name__)


class BasisAndHamiltonianChooser(QWidget):
    r"""
    Choose basis and hamiltonian
    """
    null_prompt = '- Select -'
    all_qualities = 'All Qualities'
    basis_qualities = [all_qualities, 'SZ', 'DZ', 'TZ', 'QZ', '5Z', '6Z']

    def __init__(self, parent: 'GuidedPane'):
        super().__init__(parent)
        self.parent = parent

        self.basis_registry = pymolpro.basis_registry()
        self.desired_basis_quality = self.parent.input_specification.basis_quality

        self.combo_hamiltonian = QComboBox(self)
        self.combo_hamiltonian.addItems([h['text'] for h in molpro_input.hamiltonians().values()])
        self.combo_hamiltonian.currentTextChanged.connect(self.changed_hamiltonian)

        self.guided_combo_basis_quality = QComboBox(self)
        self.guided_combo_basis_quality.addItems(self.basis_qualities)
        self.guided_combo_basis_quality.currentTextChanged.connect(self.changed_basis_quality)

        self.basis_selector = BasisSelector(self.changed_default_basis, self.null_prompt)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(RowOfTitledWidgets({
            'Hamiltonian': self.combo_hamiltonian,
            'Quality': self.guided_combo_basis_quality,
            'Basis': self.basis_selector,
        }, title='Hamiltonian and basis', alignment=Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop))

    def refresh(self):
        while True:
            if not 'basis' in self.input_specification or not 'default' in self.input_specification['basis'] or not \
                    self.input_specification['basis']['default']:
                self.input_specification['basis'] = self.default_basis_for_hamiltonian(
                    self.desired_basis_quality if self.desired_basis_quality > 0 else 3)
                continue

            core_correlation = self.input_specification[
                'core_correlation'] if 'core_correlation' in self.input_specification else 'large'
            possible_basis_sets = [k for k in self.basis_registry.keys() if (  # True or
                    self.desired_basis_quality == 0 or self.basis_registry[k][
                'quality'] == self.basis_qualities[self.desired_basis_quality]
            )
                                   and (
                                           not 'hamiltonian' in self.input_specification or
                                           self.hamiltonian_type(k) == self.input_specification[
                                               'hamiltonian']
                                   )
                                   and (
                                           core_correlation == 'mixed'
                                           or (core_correlation == 'small' and 'CV' in k)
                                           or core_correlation == 'large'
                                   )
                                   ]
            if core_correlation == 'mixed' and 'heavy' not in self.input_specification['basis']['elements']:
                self.input_specification['basis']['elements']['Heavy'] = ''
            self.basis_selector.reload(self.input_specification['basis'], possible_basis_sets,
                                       core_correlation == 'mixed')
            self.basis_selector.show()

            self.guided_combo_basis_quality.setCurrentText(self.basis_qualities[self.desired_basis_quality])
            self.combo_hamiltonian.setCurrentText(
                molpro_input.hamiltonians()[self.input_specification['hamiltonian']]['text'])
            break

    def changed_hamiltonian(self, text):
        new_hamiltonian_ = list(molpro_input.hamiltonians().keys())[
            [v['text'] for v in molpro_input.hamiltonians().values()].index(text)]
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
        quality = desired_basis_quality if desired_basis_quality > 0 else 3
        return {'default': 'cc-pV(' + self.basis_qualities[quality][0] + '+d)Z' +
                           molpro_input.hamiltonians()[self.input_specification['hamiltonian']]['basis_string'],
                'elements': {}, 'quality': quality}

    def changed_default_basis(self, spec):
        if (spec and
                'default' in spec and
                spec['default'] != self.null_prompt and
                spec['default'] != '' and
                spec != self.input_specification['basis']):
            self.input_specification['basis'] = copy.deepcopy(spec)
            self.input_specification['basis']['quality'] = self.input_specification.basis_quality
            self.write()

    def write(self):
        self.parent.refresh_input_from_specification()

    @property
    def input_specification(self):
        return self.parent.input_specification

    # @property
    # def hamiltonians(self):
    #     result = set()
    #     for keyfound in self.basis_registry.keys():
    #         if keyfound is not None:
    #             result.add(self.hamiltonian_type(keyfound))
    #     print('BasisAndHamiltonianChooser.hamiltonians:',result)
    #     return result

    def hamiltonian_type(self, key):
        return re.sub(r'\(.*', '', self.basis_registry[key]['type'])


class GuidedPane(QWidget):
    method_changed_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.project = self.parent.project
        self.input_pane = self.parent.input_pane
        self.setContentsMargins(0, 0, 0, 0)
        self.method_asserted = False

        self.guided_layout = QVBoxLayout()
        self.guided_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.guided_layout)

        self.guided_combo_orientation = QComboBox(self)
        self.guided_combo_orientation.addItems(molpro_input.orientation_options().keys())
        self.guided_combo_orientation.currentTextChanged.connect(
            lambda text: self.input_specification_change('orientation', text))

        self.charge_line = ChargeSelector()
        self.charge_line.textChanged.connect(lambda text: self.input_specification_change('charge', text))

        self.spin_line = SpinComboBox(self, 0, 14)
        self.spin_line.spin_changed.connect(
            lambda ms2: self.input_specification_change('spin', str(ms2) if ms2 >= 0 else ''))

        self.guided_combo_wave_fct_symm = QComboBox(self)
        self.guided_combo_wave_fct_symm.addItems(molpro_input.symmetry_commands().keys())
        self.guided_combo_wave_fct_symm.currentTextChanged.connect(
            lambda text: self.input_specification_change('symmetry', text))

        self.guided_combo_job_type = QComboBox(self)
        self.guided_combo_job_type.setMaximumWidth(180)
        self.guided_combo_job_type.addItems(molpro_input.job_types().values())
        self.guided_combo_job_type.currentTextChanged.connect(
            lambda text: self.input_specification_change('job_type', text))

        self.guided_combo_method = QComboBox(self)

        logger.debug('molpro_input.supported_methods(): ' + str(molpro_input.supported_methods()))
        self.guided_combo_method.addItems(molpro_input.supported_methods())
        # print('input specification',self.input_specification)
        # print('input specification method',self.input_specification['method'])
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
            'Local orbitals': self.guided_orbitals_input,
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
        self.guided_combo_orientation.setCurrentText(self.input_specification.with_defaults['orientation'])
        self.guided_combo_wave_fct_symm.setCurrentText(self.input_specification.with_defaults['symmetry'])
        if 'charge' in self.input_specification:
            self.charge_line.setText(self.input_specification['charge'])
        else:
            self.charge_line.setText('0')

        self.spin_line.refresh(self.input_specification.with_defaults['spin'])

        if self.input_specification is not None:
            if self.input_specification.method is None:
                self.input_specification.method = 'rhf'
            method_index = self.guided_combo_method.findText(
                re.sub('^df-', '', self.input_specification.method, flags=re.IGNORECASE).upper(),
                MatchFlag.MatchFixedString)
            self.guided_combo_method.setCurrentIndex(method_index)
            if re.match('[ru]ks', self.input_specification.method, flags=re.IGNORECASE):
                self.method_row.ensure_not(['Core Correlation'])
                self.method_row.ensure({'Functional': self.guided_combo_functional, })
                if not self.input_specification.density_functional:
                    self.input_specification.density_functional = self.guided_combo_functional.itemText(0)
                self.guided_combo_functional.setCurrentIndex(self.guided_combo_functional.findText(
                    self.input_specification.density_functional, MatchFlag.MatchFixedString))
            elif re.match('[ru]hf', self.input_specification.method):
                self.method_row.ensure_not(['Functional'])
                self.method_row.ensure_not(['Core Correlation'])
            else:
                self.method_row.ensure_not(['Functional'])
                self.method_row.ensure({'Core Correlation': self.guided_combo_core_correlation, })
        self.guided_combo_job_type.setCurrentText(self.input_specification['job_type'])
        if 'core_correlation' in self.input_specification:
            self.guided_combo_core_correlation.setCurrentText(self.input_specification['core_correlation'])

        self.step_options_combo.clear()
        self.step_options_combo.addItem('- Select job step -')
        self.step_options_combo.addItems([step.command.upper() for step in self.input_specification.job_steps if
                                          step.command.lower() != self.input_specification.procname.lower()])
        self.step_options_combo.setCurrentIndex(0)
        try:
            registry_df = pymolpro.procedures_registry()[self.input_specification.method.upper()][
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
            if 'ks' in value.lower():
                self.input_specification.density_functional = self.input_specification.density_functional
            self.method_changed_signal.emit(value)
            if self.parent.initialised_from_input:
                self.method_asserted = True
            self.input_specification.polish()
        elif key == 'job_type':
            self.input_specification.set_job_type([k for k, v in molpro_input.job_types().items() if v == value][0])
        elif key == 'density_functional':
            self.input_specification.density_functional = value
        elif key == 'charge':
            if value == '-': return
            try:
                old_charge = int(self.input_specification['charge'])
            except:
                old_charge = 0
            self.input_specification['charge'] = int(value)
            if int(value) != old_charge and 'spin' in self.input_specification:
                self.input_specification.pop('spin')
        elif key == 'spin':
            if value is not None and int(value) >= 0:
                self.input_specification['spin'] = int(value)
            else:
                if 'spin' in self.input_specification: self.input_specification.pop('spin')
        else:
            self.input_specification[key] = value
            if key == 'properties':
                self.input_specification.polish()
        self.refresh_input_from_specification()
        self.refresh()

    def input_specification_variable_change(self, key, value):
        if 'variables' not in self.input_specification:
            self.input_specification['variables'] = {}

        self.input_specification['variables'][key] = value
        if key == 'charge':
            self.refresh()

        self.refresh_input_from_specification()

    def refresh_input_from_specification(self):
        # logger.debug('refresh_input_from_specification')
        if not self.parent.guided_possible(): return
        new_input = self.input_specification.molpro_input()
        if not molpro_input.equivalent(self.input_pane.toPlainText(), new_input):
            self.input_pane.setPlainText(new_input)

    def thresholds_edit(self, flag):
        project_registry = pymolpro.registry('THRESH')
        available_options = [k.split(',')[0] for k in project_registry]
        title = 'Global thresholds'
        box = OptionsDialog(
            self.parent.input_specification['thresholds'] if 'thresholds' in self.parent.input_specification else {},
            {o.lower(): '' for o in available_options}, title=title, parent=self,
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
            {o.lower(): '' for o in available_options}, title=title, parent=self,
            help_uri='https://www.molpro.net/manual/doku.php?id=program_control#global_print_options_gprint_nogprint')
        result = box.exec()
        if result is not None:
            self.parent.input_specification['prints'] = result
            self.refresh_input_from_specification()

    def step_options_edit(self, step: int):
        if step < 0: return
        step_ = self.parent.input_specification.job_steps[step]
        method_ = step_.command.upper()
        available_options = {}
        for option in list(
                pymolpro.procedures_registry()[re.sub('^HF', 'RHF', method_.replace('FREQUENCIES', 'FREQ'))][
                    'options']):
            available_options[re.sub('.*:', '', option.split('=')[0])] = (option.split('=') + [''])[1]
        title = 'Options for step ' + str(step + 1) + ' (' + method_ + ')'
        existing_options = {o.split('=')[0]: o.split('=')[1] if len(o.split('=')) > 1 else '' for o in step_.options}
        box = OptionsDialog(existing_options, available_options, title=title, parent=self,
                            help_uri='https://www.molpro.net/manual/doku.php?q=' + method_ + '&do=search')
        result = box.exec()
        if result is not None:
            step_.options = [k + '=' + v if v else k for k, v in result.items()]
            self.parent.input_specification.set_job_step(step_, step)
            self.refresh_input_from_specification()
        self.step_options_combo.setCurrentIndex(0)


class RowOfTitledWidgets(QWidget):
    def __init__(self, widgets, title=None, parent=None, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(parent)
        self.alignment = alignment
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
                self.layout2.addWidget(self.widget_captions[k], 0, len(self.widgets), alignment=self.alignment)
                self.layout2.addWidget(v, 1, len(self.widgets), alignment=self.alignment)
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
        self.addItems([o['text'] for k, o in molpro_input.local_orbital_types().items() if
                       k != 'nbo' or self.parent.input_specification.open_shell_electrons is None or self.parent.input_specification.open_shell_electrons == 0])
        if 'orbitals' in self.parent.input_specification:
            for o in self.parent.input_specification['orbitals']:
                for i in range(self.model().rowCount()):
                    if self.model().item(i).text() == molpro_input.local_orbital_types()[o]['text']:
                        self.model().item(i).setCheckState(CheckState.Checked)
        self.updateText()

    def action(self, text):
        self.parent.input_specification['orbitals'] = [k for k, v in molpro_input.local_orbital_types().items() for t in
                                                       self.currentData() if t == v['text']]
        if any([b in self.parent.input_specification['orbitals'] for b in ['nbo', 'ibo']]):
            self.parent.input_specification_change('symmetry', 'none')
        self.parent.refresh_input_from_specification()


class InputCombo(CheckableComboBox):
    r"""
    Helper for constructing input
    """

    def __init__(self, identity, parent=None):
        super().__init__(parent, null_text='None')
        self.parent = parent
        self.identity = identity
        self.addItems(getattr(molpro_input, self.identity).keys())
        if identity in self.parent.input_specification:
            for o in self.parent.input_specification[identity]:
                for i in range(self.model().rowCount()):
                    if self.model().item(i).text() == o:
                        self.model().item(i).setCheckState(CheckState.Checked)
        self.model().dataChanged.connect(self.refresh)

    def refresh(self, text):
        self.parent.input_specification[self.identity] = [k for k, v in getattr(molpro_input, self.identity).items() for
                                                          t in
                                                          self.currentData() if t == k]
        self.parent.input_specification.polish()
        self.parent.refresh_input_from_specification()


class PropertyInput(InputCombo):
    r"""
    Helper for constructing input for properties
    """

    def __init__(self, parent=None):
        super().__init__('properties', parent)


class ChargeSelector(QWidget):
    textChanged = pyqtSignal(str, name='textChanged')

    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.label = QLabel('0')
        self.plus_button = QToolButton()
        self.plus_button.setArrowType(UpArrow)
        self.minus_button = QToolButton()
        self.minus_button.setArrowType(DownArrow)
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
