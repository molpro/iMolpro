from utilities import mixed_core_correlation_only_valence
from pymolpro.defbas import periodic_table
import pytest
def test_mixed_core_correlation_only_valence():

    assert periodic_table.index('Zn')+1 == 30

    for range in [
        'Ga',
        31,
        'Ga-Kr',
        999,
        -1,
    ]:
        assert mixed_core_correlation_only_valence(range)

    for range in [
        'Zn',
        30,
        'Zn-Ga',
        'Zn-Kr',
        'Kr-Ga',
        'Ga-Xe',
    ]:
        assert not mixed_core_correlation_only_valence(range)

    for range in [
        'bad',
        'bad-worse',
        4.0,
        {'a':'b'},
        True,
    ]:
        with pytest.raises(ValueError):
            mixed_core_correlation_only_valence(range)
