from types import SimpleNamespace

from iMolpro.vtk_molecule_widget import orbitals_by_energy, orbital_label, initial_orbital, contour_cube_key_usable


def _orbital(ID, energy):
    return SimpleNamespace(ID=ID, energy=energy)


def test_orbitals_sorted_by_energy_stable_for_ties():
    a, b, c, d = _orbital('1.1', -11.2), _orbital('3.7', -0.19), _orbital('2.1', -1.0), _orbital('1.2', -1.0)
    assert orbitals_by_energy([b, c, a, d]) == [a, c, d, b]


def test_orbital_label_shows_id_and_energy():
    assert orbital_label(_orbital('3.7', -0.191234)) == '3.7   (-0.1912)'
    assert orbital_label(SimpleNamespace(ID='4.1')) == '4.1'


def test_initial_orbital_is_highest_energy_or_last_on_ties():
    homo = _orbital('3.7', -0.19)
    assert initial_orbital([_orbital('1.1', -11.2), homo, _orbital('2.1', -1.0)]) is homo
    natural = [_orbital(f'{i}.1', 0.0) for i in range(1, 4)]
    assert initial_orbital(natural) is natural[-1]


def test_cached_cube_reusable_only_for_same_orbital_grid_and_not_lower_contour():
    orbital, other = _orbital('1.1', -1.0), _orbital('2.1', -0.5)
    key = (orbital, 60, 0.05)
    assert contour_cube_key_usable(key, orbital, 60, 0.05)
    assert contour_cube_key_usable(key, orbital, 60, 0.1)
    assert not contour_cube_key_usable(key, orbital, 60, 0.02)
    assert not contour_cube_key_usable(key, orbital, 75, 0.05)
    assert not contour_cube_key_usable(key, other, 60, 0.05)
