import pytest

from iMolpro import babel

WATER_PDB = """HETATM    1  O   HOH A   1       0.000   0.000   0.117  1.00  0.00           O
HETATM    2  H   HOH A   1       0.000   0.757  -0.469  1.00  0.00           H
HETATM    3  H   HOH A   1       0.000  -0.757  -0.469  1.00  0.00           H
END
"""

needs_openbabel = pytest.mark.skipif(not babel.available(), reason='openbabel not installed')


def test_xyz_always_offered():
    assert babel.suffixes()[0] == 'xyz'
    assert '*.xyz' in babel.file_dialog_filter()


@needs_openbabel
def test_many_formats_offered():
    assert {'pdb', 'mol2', 'sdf', 'cif'} <= set(babel.suffixes())


@needs_openbabel
def test_pdb_to_xyz(tmp_path):
    source = tmp_path / 'water.pdb'
    source.write_text(WATER_PDB)
    destination = tmp_path / 'out'
    destination.mkdir()
    result = babel.to_xyz(source, destination)
    assert result == str(destination / 'water.xyz')
    lines = (destination / 'water.xyz').read_text().splitlines()
    assert lines[0].strip() == '3'
    assert [line.split()[0] for line in lines[2:5]] == ['O', 'H', 'H']
    assert float(lines[2].split()[3]) == pytest.approx(0.117)


@needs_openbabel
def test_unknown_suffix(tmp_path):
    source = tmp_path / 'water.notaformat'
    source.write_text(WATER_PDB)
    with pytest.raises(ValueError):
        babel.to_xyz(source, tmp_path)
