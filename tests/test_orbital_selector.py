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


def test_orbital_label_pads_id_so_columns_line_up():
    assert orbital_label(_orbital('3.7', -0.19123), id_width=5) == '3.7   [2.000] (-0.1912)'
    assert orbital_label(_orbital('102.1', -0.29214, 1.30712), id_width=5) == '102.1 [1.307] (-0.2921)'


def test_orbital_list_rows_data_marks_and_height(qtbot):
    from iMolpro.vtk_molecule_widget import OrbitalList
    orbitals = [_orbital(f'{i}.1', -1.0 / i) for i in range(1, 16)]
    widget = OrbitalList(orbitals, visible_rows=10)
    qtbot.addWidget(widget)
    assert widget.count() == 15
    assert widget.orbital_id(0) == '1.1' and widget.orbital_id(14) == '15.1'
    assert widget.orbital_id(15) is None
    assert widget.item(0).text().startswith('1.1  [2.000]')
    assert widget.item(0).icon().cacheKey() != 0
    widget.set_marked(3, True)
    assert widget.item(3).icon().cacheKey() != widget.item(0).icon().cacheKey()
    row_height = widget.sizeHintForRow(0)
    assert 10 * row_height <= widget.height() < 11 * row_height
    short = OrbitalList(orbitals[:3])
    qtbot.addWidget(short)
    assert short.height() < 4 * short.sizeHintForRow(0)


def test_beta_orbitals_keyed_with_minus_but_named_with_beta(qtbot):
    from lxml import etree
    from iMolpro.vtk_molecule_widget import OrbitalList, orbital_key, orbital_name
    root = etree.fromstring('<m><orbitals spin="alpha"><orbital/></orbitals>'
                            '<orbitals spin="beta"><orbital/></orbitals></m>')
    alpha_node, beta_node = root.xpath('//orbital')
    alpha = SimpleNamespace(ID='1.1', energy=-0.5, occupation=1.0, node=alpha_node)
    beta = SimpleNamespace(ID='1.1', energy=-0.4, occupation=1.0, node=beta_node)
    assert orbital_key(alpha) == '1.1' and orbital_key(beta) == '-1.1'
    assert orbital_name(alpha) == '1.1\u03b1' and orbital_name(beta) == '1.1\u03b2'
    assert orbital_label(beta) == '1.1\u03b2 [1.000] (-0.4000)'
    widget = OrbitalList(orbitals_in_display_order([alpha, beta]))
    qtbot.addWidget(widget)
    assert [widget.orbital_id(row) for row in range(2)] == ['-1.1', '1.1']
    assert widget.item(1).text() == '1.1\u03b1 [1.000] (-0.5000)'


def test_spin_free_orbitals_get_no_spin_letter():
    from lxml import etree
    from iMolpro.vtk_molecule_widget import orbital_name
    node = etree.fromstring('<m><orbitals spin="closed" type="NATURAL"><orbital/></orbitals></m>').xpath('//orbital')[0]
    natural = SimpleNamespace(ID='3.1', energy=0.0, occupation=1.0, node=node)
    assert orbital_name(natural) == '3.1'
    assert orbital_label(natural) == '3.1 [1.000] (0.0000)'
