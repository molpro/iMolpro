import sys
import pubchempy
from PyQt5.QtWidgets import QVBoxLayout, QDialog, QDialogButtonBox, QLabel, QComboBox, QLineEdit


class PubChemSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Search PubChem')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.value = QLineEdit()
        self.value.setMaxLength(50)
        self.value.setPlaceholderText('Enter search text here')
        self.layout.addWidget(self.value)

        self.key = QComboBox()
        self.key.addItems(['name', 'formula', 'inchi', 'inchikey', 'sdf', 'smiles', 'cid'])
        self.layout.addWidget(self.key)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)


class PubChemFetchDialog(QDialog):
    def __init__(self, query, field='name', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select from PubChem search results')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        def matches(i):
            if i == 0:
                return 'no matches'
            elif i == 1:
                return '1 match'
            else:
                return str(i) + ' matches'

        self.compounds = pubchempy.get_compounds(query, field, record_type='3d')
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
        else:
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

