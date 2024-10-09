import os
import pathlib

from lxml import etree
from PyQt5.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, \
    QGridLayout, QFormLayout, QMessageBox
from pysjef import Project

import settings
from help import help_dialog


def sanitise_backends(parent):
    dot_molpro= pathlib.Path(settings.settings.filename).parent
    teaching_molpro_path = dot_molpro / 'teach' / 'bin' / 'molpro'
    if hasattr(sys, '_MEIPASS') and platform.uname().system != 'Windows':
        teaching_molpro_path = os.path.normpath(os.path.join(
            sys._MEIPASS, 'molpro', 'bin', 'molpro'
        ))
    teaching_molpro = teaching_molpro_path.exists()
    regular_molpro = False
    for path in os.environ['PATH'].split(os.pathsep):
        regular_molpro = regular_molpro or (pathlib.Path(path) / 'molpro').exists()
    if teaching_molpro:
        name = 'teach' if regular_molpro else 'local'
        if name not in parent.project.backend_names():
            new_backend(name, name=name, molpro_path=str(teaching_molpro_path), molpro_options='{-m %m!Process memory}')
            parent.project.refresh_backends()
        else:
            run_command = parent.project.backend_get(name, 'run_command')
            if str(teaching_molpro_path) not in run_command:
                delete_backend(name)
                new_backend(name, name=name, molpro_path=str(teaching_molpro_path), molpro_options='{-m %m!Process memory}')
                parent.project.refresh_backends()


def configure_backend(parent):
    class BackendDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            backend = parent.project.property_get('backend')
            if backend:
                self.backend = backend['backend']
            else:
                self.backend = 'local'
            self.setWindowTitle('Run parameters for backend ' + self.backend)
            self.change_backend_box = QComboBox()
            self.change_backend_box.addItems(parent.project.backend_names())
            backend_index = parent.project.backend_names().index(self.backend)
            self.change_backend_box.setCurrentIndex(backend_index)
            parameters = parent.project.backend_parameters(self.backend)
            parameters_doc = parent.project.backend_parameters(self.backend, doc=True)

            self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)
            self.layout = QVBoxLayout()
            run_text = QLabel(
                'Current backend ' + self.backend + ' submission command:\n' + parent.project.backend_get(self.backend,
                                                                                                          'run_command') + '\nHost: ' + parent.project.backend_get(
                    self.backend, 'host'))
            run_text.setWordWrap(True)
            self.layout.addWidget(run_text)
            if parameters:
                grid_layout = QGridLayout()
                self.parameter_values = {}
                row = 0
                for k in parameters.keys():
                    if v := parent.project.backend_parameter_get(self.backend, k):
                        parameters[k] = v
                    self.parameter_values[k] = QLineEdit(self)
                    self.parameter_values[k].setText(parameters[k])
                    grid_layout.addWidget(QLabel(k), row, 0)
                    grid_layout.addWidget(self.parameter_values[k], row, 1)
                    grid_layout.addWidget(QLabel(parameters_doc[k]), row, 2)
                    row += 1
                self.layout.addLayout(grid_layout)
            self.switch_layout = QHBoxLayout()
            self.switch_layout.addWidget(QLabel('Change to backend:'))
            self.switch_layout.addWidget(self.change_backend_box)
            self.layout.addLayout(self.switch_layout)
            # self.layout.addWidget(self.rawedit)
            self.layout.addWidget(self.button_box)
            self.setLayout(self.layout)

        def changed_backend(self):
            return self.change_backend_box.currentText()

    result = None
    while (dlg := BackendDialog(parent)) and (result := dlg.exec()) and dlg.changed_backend() != \
            parent.project.property_get('backend')['backend']:
        parent.project.property_set({'backend': dlg.changed_backend()})

    if result:
        parameters = parent.project.backend_parameters(dlg.backend)
        for parameter in parameters.keys():
            if dlg.parameter_values[parameter].text():
                parent.project.backend_parameter_set(dlg.backend, parameter, dlg.parameter_values[parameter].text())


class BackendConfigurationEditor(QDialog):
    choose = '- Choose below -'

    def __init__(self, file, parent):
        super().__init__(parent)
        # win = MainEditFile(file)
        # win.setMinimumSize(600, 400)
        self.file = file
        self.parent = parent

        self.layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.layout.addLayout(form_layout)
        self.setWindowTitle('Configuration of backends')
        self.edit_combo = QComboBox()
        self.edit_combo.addItem(self.choose)
        self.edit_combo.addItems(self.backends)
        self.edit_combo.currentTextChanged.connect(self.edit)
        form_layout.addRow('Edit or delete:', self.edit_combo)
        self.new_combo = QComboBox()
        self.new_combo.addItems([self.choose, 'local', 'remote linux', 'Slurm', 'Other'])
        self.new_combo.currentTextChanged.connect(self.new)
        form_layout.addRow('New:', self.new_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Help)
        self.buttons.accepted.connect(self.close)
        self.buttons.clicked.connect(self.clicked)
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

    @property
    def backends(self):
        backends_ = [backend.get('name') for backend in (etree.parse(self.file).xpath('//backend'))]
        return backends_

    def edit(self, text):
        if not text or text == self.choose: return
        dlg = BackendEditor(text, self)
        result = dlg.exec()
        self.edit_combo.setCurrentText(self.choose)

    def new(self, text):
        if not text or text == self.choose: return
        name = new_backend(text, self.file)
        self.parent.project.refresh_backends()
        self.reset(name)


    def reset(self, name):
        self.edit_combo.clear()
        self.edit_combo.addItem(self.choose)
        self.edit_combo.addItems(self.backends)
        self.edit_combo.setCurrentText(name)
        self.new_combo.setCurrentText(self.choose)

    def clicked(self, button):
        if button == self.buttons.button(QDialogButtonBox.Help):
            help_dialog('doc/backends.md', self)

def delete_backend(name, file=None):
    if file is None:
        file = str(pathlib.Path.home() / '.sjef/molpro/backends.xml')
    root = etree.parse(file)
    node = root.xpath('//backend[@name="' + name + '"]')[0]
    node.getparent().remove(node)
    root.write(file, pretty_print=True, xml_declaration=True, encoding='utf-8')

def new_backend(text='local', file=None, name=None, molpro_path='molpro', molpro_options=' {-n %n!MPI size} {-M %M!Total memory} {-m %m!Process memory} {-G %G!GA memory}'):
    if file is None:
        file = str(pathlib.Path.home() / '.sjef/molpro/backends.xml')
    root = etree.parse(file)
    n = etree.SubElement(root.getroot(), 'backend')
    sequence = 1
    backends_ = [backend.get('name') for backend in (etree.parse(file).xpath('//backend'))]
    while text.replace(' ', '_') + '_' + str(sequence) in backends_:
        sequence += 1
    name_ = text.replace(' ', '_') + '_' + str(sequence) if name is None else name
    n.set('name', name_)
    n.set('run_command', molpro_path + ' ' + molpro_options)
    if text == 'remote linux' or text == 'Slurm':
        n.set('host', 'someone@some.computer.somewhere')
    if text == 'Slurm':
        n.set('run_command', 'your_job_submission_script')
        n.set('run_jobnumber', 'Submitted batch job *([0-9]+)')
        n.set('kill_command', 'scancel')
        n.set('status_command', 'squeue -j')
        n.set('status_running', ' (CF|CG|R|ST|S) *[0-9]')
        n.set('status_waiting', ' (PD|SE) *[0-9]')
    if text != 'local' and text != 'teach':
        n.set('cache', '.cache/sjef')
    root.write(file, pretty_print=True, xml_declaration=True, encoding='utf-8')
    return name_


class BackendEditor(QDialog):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.parent = parent
        self.setWindowTitle('Configure backend ' + backend)
        layout = QVBoxLayout()
        et = etree.parse(parent.file).xpath('//backend[@name="' + backend + '"]')[0]
        self.fields = {field: QLineEdit(et.get(field)) for field in
                       ['name', 'run_command', 'host', 'cache', 'kill_command', 'status_command', 'run_jobnumber',
                        'status_running', 'status_waiting']}
        for e in self.fields.values():
            e.setFixedWidth(400)
            e.setCursorPosition(0)
        self.fields['name'].setFixedWidth(150)
        form_layout = QFormLayout()
        for field, editor in self.fields.items():
            form_layout.addRow(field, editor)
        layout.addLayout(form_layout)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Help | QDialogButtonBox.Cancel | QDialogButtonBox.Discard | QDialogButtonBox.Ok)
        self.buttons.button(QDialogButtonBox.Discard).setText('Delete')
        self.buttons.accepted.connect(self.act)
        self.buttons.rejected.connect(self.close)
        self.buttons.clicked.connect(self.clicked)

        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def act(self):
        root = etree.parse(self.parent.file)
        backend_node = root.xpath('//backend[@name="' + self.backend + '"]')[0]
        for field, editor in self.fields.items():
            if editor.text():
                backend_node.set(field, editor.text())
            elif backend_node.get(field):
                del backend_node.attrib[field]
        root.write(self.parent.file, pretty_print=True, xml_declaration=True, encoding='utf-8')
        self.parent.reset(self.parent.choose)
        self.close()

    def clicked(self, button):
        if button == self.buttons.button(QDialogButtonBox.Discard):
            if QMessageBox.question(self, 'Confirm', 'Are you sure you want to delete backend ' + self.backend + '?',
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                root = etree.parse(self.parent.file)
                node = root.xpath('//backend[@name="' + self.backend + '"]')[0]
                node.getparent().remove(node)
                root.write(self.parent.file, pretty_print=True, xml_declaration=True, encoding='utf-8')
                self.parent.reset(self.parent.choose)
                self.close()
        elif button == self.buttons.button(QDialogButtonBox.Help):
            help_dialog('doc/backends.md', self)
