import os
import pathlib
import re

from settings import settings
import pubchempy
from chemspipy import ChemSpider
import tempfile
from PyQt5.QtWidgets import QVBoxLayout, QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit, QCheckBox, \
    QHBoxLayout, QInputDialog


class DatabaseSearchDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Search online structure databases')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel('Give molecule name, formula, InChi, InChiKey, SMILES or PubChem cid'))
        self.value = QLineEdit()
        self.value.setMinimumWidth(180)
        self.value.setPlaceholderText('Enter search text here')
        self.layout.addWidget(self.value)

        self.pubchem_checkbox = QCheckBox(self)
        self.pubchem_checkbox.setText('PubChem')
        self.pubchem_checkbox.setChecked(True)
        self.chemspider_checkbox = QCheckBox(self)
        self.chemspider_checkbox.setText('ChemSpider')
        self.chemspider_checkbox.setChecked('CHEMSPIDER_API_KEY' in settings)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(QLabel('Databases: '))
        checkbox_layout.addWidget(self.pubchem_checkbox)
        checkbox_layout.addWidget(self.chemspider_checkbox)
        checkbox_layout.addStretch()
        self.layout.addLayout(checkbox_layout)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonbox)


class DatabaseFetchDialog(QDialog):
    def __init__(self, query, use_pubchem=True, use_chemspider=True):
        super().__init__()
        self.setWindowTitle('Select from database search results')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        def matches(i):
            if i == 0:
                return 'no matches'
            elif i == 1:
                return '1 match'
            else:
                return str(i) + ' matches'

        if use_pubchem:
            self.database = 'PubChem'
            for field in ['name', 'cid', 'inchi', 'inchikey', 'sdf', 'smiles', 'formula', ]:
                if field == 'cid' and not all(chr.isdigit() for chr in query.strip()): continue
                if field == 'inchi' and query.strip()[:3] != '1S/': continue
                try:
                    self.compounds = pubchempy.get_compounds(query.strip(), field, record_type='3d')
                except Exception:
                    self.layout.addWidget(QLabel('Network or other error during PubChem search'))
                    self.buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
                    self.buttonbox.rejected.connect(self.reject)
                    self.layout.addWidget(self.buttonbox)
                    return
                if self.compounds: break
            self.layout.addWidget(
                QLabel('PubChem found ' + matches(len(self.compounds)) + ' to ' + field + '=' + query))
            if self.compounds:
                self.chooser = QComboBox()
                self.chooser.addItems(
                    [str(compound.cid) + ' (' + ', '.join(compound.synonyms)[:50] + '...)' for compound in
                     self.compounds])
                self.layout.addWidget(self.chooser)
                self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                self.buttonbox.accepted.connect(self.accept)
                self.buttonbox.rejected.connect(self.reject)
                self.layout.addWidget(self.buttonbox)
                return

        if use_chemspider:
            if 'CHEMSPIDER_API_KEY' not in settings:
                text, ok = QInputDialog().getText(self, 'ChemSpider API key',
                                                  'To use ChemSpider, give the value of your API key - see https://developer.rsc.org/')
                if ok and text:
                    settings['CHEMSPIDER_API_KEY'] = text

            if 'CHEMSPIDER_API_KEY' in settings:
                cs = ChemSpider(settings['CHEMSPIDER_API_KEY'])
                self.database = 'ChemSpider'
                self.compounds = cs.search(query)
                self.layout.addWidget(
                    QLabel('ChemSpider found ' + matches(len(self.compounds)) + ' for ' + query))
                if self.compounds:
                    self.chooser = QComboBox()
                    self.chooser.addItems(
                        [str(compound.csid) + ' (' + compound.common_name + ')' for compound in self.compounds])
                    self.layout.addWidget(self.chooser)
                    self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    self.buttonbox.accepted.connect(self.accept)
                    self.buttonbox.rejected.connect(self.reject)
                    self.layout.addWidget(self.buttonbox)
                    return

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttonbox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonbox)

    def xyz(self, index=None):
        index_ = index if index else self.chooser.currentIndex()

        def s(x):
            return f'{x:.8f}'

        compound = self.compounds[index_]

        if self.database == 'PubChem':
            record = compound.record
            conformer = record['coords'][0]['conformers'][0]
            xyz = str(len(compound.elements)) + '\n' + 'PubChem cid=' + str(compound.cid) + '\n'
            for key, element in enumerate(compound.elements):
                xyz += element + ' ' + s(conformer['x'][key]) + ' ' + s(conformer['y'][key]) + ' ' + \
                       s(conformer['z'][key]) + '\n'
            return xyz

        if self.database == 'ChemSpider':
            lines = compound.mol_3d.split('\n')
            n = int(lines[3].strip().split(' ')[0].strip())
            xyz = str(n) + '\nChemSpider ' + str(compound.csid) + '\n'
            for i in range(4, n + 4):
                split = re.sub(' +', ' ', lines[i].strip()).split(' ')
                xyz += split[3] + ' ' + ' '.join(split[:3]) + '\n'
            return xyz

    def cid(self, index=None):
        index_ = index if index else self.chooser.currentIndex()
        if self.database == 'PubChem':
            return self.compounds[index_].cid
        elif self.database == 'ChemSpider':
            return self.compounds[index_].csid


def database_choose_structure():
    r"""
    Interactively search for a structure in available databases.
    :return: If not found, or cancelled, None. Otherwise, create a file containing the xyz, and return its name
    """
    dlg = DatabaseSearchDialog()
    dlg.exec()
    if dlg.result():
        dlg2 = DatabaseFetchDialog(dlg.value.text(), dlg.pubchem_checkbox.isChecked(),
                                   dlg.chemspider_checkbox.isChecked())
        dlg2.exec()
        if dlg2.result():
            filename = pathlib.Path(tempfile.mkdtemp()) / (dlg2.database + '-' + str(dlg2.cid()) + '.xyz')
            open(filename, 'w').write(dlg2.xyz())
            return filename
