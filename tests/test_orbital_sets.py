from types import SimpleNamespace

from iMolpro.output_tabs import drop_contained_orbital_sets


def _orbital(ID, energy=-0.5, occupation=2.0, xyz=(0.0, 0.0, 0.0)):
    return SimpleNamespace(ID=ID, energy=energy, occupation=occupation, atoms=[{'xyz': xyz}])


def _set(orbitals, type_='CANONICAL', method='RHF', stateID='1'):
    return [orbitals, {'method': method, 'type': type_, 'stateID': stateID}, None]


def test_occupied_copy_dropped_in_favour_of_copy_with_virtuals():
    occupied = [_orbital('1.1', -1.0), _orbital('2.1', -0.5)]
    full = occupied + [_orbital('3.1', 0.2, 0.0)]
    jobstep, put = _set(list(occupied)), _set(list(full))
    natural = _set(list(occupied), 'NATURAL')
    assert drop_contained_orbital_sets([jobstep, natural, put]) == [natural, put]


def test_identical_copies_keep_the_first():
    first, second = _set([_orbital('1.1')]), _set([_orbital('1.1')])
    assert drop_contained_orbital_sets([first, second]) == [first]


def test_sets_differing_in_energy_method_state_or_geometry_are_kept():
    base = _set([_orbital('1.1', -1.0)])
    other_energy = _set([_orbital('1.1', -1.1), _orbital('2.1')])
    other_method = _set([_orbital('1.1', -1.0), _orbital('2.1')], method='UHF')
    other_state = _set([_orbital('1.1', -1.0), _orbital('2.1')], stateID='2')
    other_geometry = _set([_orbital('1.1', -1.0, xyz=(0.0, 0.0, 0.1)), _orbital('2.1')])
    sets = [base, other_energy, other_method, other_state, other_geometry]
    assert drop_contained_orbital_sets(sets) == sets


def test_beta_orbitals_distinguished_from_alpha():
    from lxml import etree
    root = etree.fromstring('<m><orbitals spin="alpha"><orbital/></orbitals>'
                            '<orbitals spin="beta"><orbital/></orbitals></m>')
    alpha_node, beta_node = root.xpath('//orbital')
    alpha = SimpleNamespace(ID='1.1', energy=-0.5, occupation=1.0, node=alpha_node, atoms=[])
    beta = SimpleNamespace(ID='1.1', energy=-0.5, occupation=1.0, node=beta_node, atoms=[])
    alpha_only, beta_only = _set([alpha], 'ALPHA+BETA', 'UHF'), _set([beta], 'ALPHA+BETA', 'UHF')
    assert drop_contained_orbital_sets([alpha_only, beta_only]) == [alpha_only, beta_only]


def test_occupied_orbitals_keep_pymolpro_evaluate():
    from iMolpro.vtk_molecule_widget import evaluable_at_any_occupation
    occupied = SimpleNamespace(ID='1.1', occupation=2.0, node=object(), evaluate='original')
    assert evaluable_at_any_occupation(occupied).evaluate == 'original'


import pathlib
import pytest

UHF_XML = pathlib.Path(__file__).parent.parent / 'sandbox' / 'nh2.344969-20261128.xml'


@pytest.mark.skipif(not UHF_XML.is_file(), reason='sandbox UHF example with virtual orbitals not present')
def test_virtual_orbital_evaluates(tmp_path):
    import numpy as np
    from iMolpro.project import Project
    from iMolpro.vtk_molecule_widget import evaluable_at_any_occupation
    project = Project(location=str(tmp_path), files=[str(UHF_XML), str(UHF_XML) + '-sidecar'])
    virtual = next(orbital for orbital in project.orbitals(1, orbital_instance=0, minocc=float('-inf'))
                   if orbital.occupation == 0.0)
    values = evaluable_at_any_occupation(virtual).evaluate(np.array([[0.0, 0.0, 0.5]]), values=True)
    assert values.shape == (1,) and np.isfinite(values).all()
