import os
import pathlib
import sys
import pubchempy
import tempfile
from PyQt5.QtWidgets import QVBoxLayout, QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit


class DatabaseSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Search online structure databases')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel('Give molecule name, formula, InChi, InChiKey, SMILES or PubChem cid'))
        self.value = QLineEdit()
        self.value.setMinimumWidth(180)
        self.value.setPlaceholderText('Enter search text here')
        self.layout.addWidget(self.value)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)


class DatabaseFetchDialog(QDialog):
    def __init__(self, query, parent=None, usePubChem=True, useChemSpider=True):
        super().__init__(parent)
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

        if usePubChem:
            self.database='PubChem'
            for field in ['name', 'cid', 'inchi', 'inchikey', 'sdf', 'smiles', 'formula', ]:
                if field == 'cid' and not all(chr.isdigit() for chr in query.strip()): continue
                if field == 'inchi' and query.strip()[:3] != '1S/': continue
                try:
                    self.compounds = pubchempy.get_compounds(query.strip(), field, record_type='3d')
                except Exception as e:
                    self.layout.addWidget(QLabel('Network or other error during PubChem search'))
                    self.buttonBox = QDialogButtonBox(QDialogButtonBox.Cancel)
                    self.buttonBox.rejected.connect(self.reject)
                    self.layout.addWidget(self.buttonBox)
                    return
                if self.compounds: break
            self.layout.addWidget(QLabel('PubChem found ' + matches(len(self.compounds)) + ' to ' + field + '=' + query))
            if self.compounds:
                self.chooser = QComboBox()
                self.chooser.addItems(
                    [str(result.cid) + ' (' + ', '.join(result.synonyms)[:50] + '...)' for result in self.compounds])
                self.layout.addWidget(self.chooser)
                self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                self.buttonBox.accepted.connect(self.accept)
                self.buttonBox.rejected.connect(self.reject)
                self.layout.addWidget(self.buttonBox)
                return

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)

    def xyz(self, index=None):
        index_ = index if index else self.chooser.currentIndex()

        def s(x):
            return f'{x:.8f}'

        compound = self.compounds[index_]
        record = compound.record
        conformer = record['coords'][0]['conformers'][0]
        xyz = str(len(compound.elements)) + '\n' + 'PubChem cid=' + str(compound.cid) + '\n'
        for key, element in enumerate(compound.elements):
            xyz += element + ' ' + s(conformer['x'][key]) + ' ' + s(conformer['y'][key]) + ' ' + \
                   s(conformer['z'][key]) + '\n'
        return xyz

    def cid(self, index=None):
        index_ = index if index else self.chooser.currentIndex()
        return self.compounds[index_].cid


def database_choose_structure():
    r"""
    Interactively search for a structure in available databases.
    :return: If not found, or cancelled, None. Otherwise, create a file containing the xyz, and return its name
    """
    dlg = DatabaseSearchDialog()
    dlg.exec()
    if dlg.result():
        dlg2 = DatabaseFetchDialog(dlg.value.text())
        dlg2.exec()
        if dlg2.result():
            filename = pathlib.Path(tempfile.mkdtemp()) / (dlg2.database() + '-' + str(dlg2.cid()) + '.xyz')
            open(filename, 'w').write(dlg2.xyz())
            return filename
