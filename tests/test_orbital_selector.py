from types import SimpleNamespace

from iMolpro.vtk_molecule_widget import orbitals_in_display_order, orbital_label, initial_orbital, \
    contour_cube_key_usable


def _orbital(ID, energy, occupation=2.0):
    return SimpleNamespace(ID=ID, energy=energy, occupation=occupation)


def test_display_order_occupation_ascending_then_energy_descending():
    core, homo, mid = _orbital('1.1', -11.2), _orbital('3.7', -0.19), _orbital('2.1', -1.0)
    assert orbitals_in_display_order([core, homo, mid]) == [homo, mid, core]
    weak, strong = _orbital('102.1', 0.0, 0.02), _orbital('5.1', 0.0, 1.95)
    single = _orbital('4.1', -0.3, 1.0)
    assert orbitals_in_display_order([strong, core, single, weak]) == [weak, single, strong, core]


def test_display_order_stable_for_full_ties():
    natural = [_orbital(f'{i}.1', 0.0, 1.0) for i in range(1, 4)]
    assert orbitals_in_display_order(natural) == natural


def test_orbital_label_shows_id_occupation_and_energy():
    assert orbital_label(_orbital('102.1', -0.29214, 1.30712)) == '102.1 [1.307] (-0.2921)'
    assert orbital_label(SimpleNamespace(ID='4.1', energy=-0.5)) == '4.1 (-0.5000)'
    assert orbital_label(SimpleNamespace(ID='4.1')) == '4.1'


def test_initial_orbital_is_top_of_selector():
    homo = _orbital('3.7', -0.19)
    assert initial_orbital([_orbital('1.1', -11.2), homo, _orbital('2.1', -1.0)]) is homo
    weak = _orbital('9.1', 0.0, 0.05)
    assert initial_orbital([_orbital('5.1', 0.0, 1.9), weak]) is weak


def test_cached_cube_reusable_only_for_same_orbital_grid_and_not_lower_contour():
    orbital, other = _orbital('1.1', -1.0), _orbital('2.1', -0.5)
    key = (orbital, 60, 0.05)
    assert contour_cube_key_usable(key, orbital, 60, 0.05)
    assert contour_cube_key_usable(key, orbital, 60, 0.1)
    assert not contour_cube_key_usable(key, orbital, 60, 0.02)
    assert not contour_cube_key_usable(key, orbital, 75, 0.05)
    assert not contour_cube_key_usable(key, other, 60, 0.05)
