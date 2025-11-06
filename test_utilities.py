from utilities import mixed_core_correlation_assert
from pymolpro.defbas import periodic_table
import pytest
def test_mixed_core_correlation_only_valence():

    assert periodic_table.index('Zn')+1 == 30

    for range in [
        'ga',
        'GA',
        'Ga',
        31,
        'Ga-Kr',
        999,
        -1,
        'Zn-Ga',
        'Zn-Kr',
        'Ga-Xe',
    ]:
        assert mixed_core_correlation_assert(range, False)

    for range in [
        'Zn',
        30,
        'Sc-Zn',
        'Na-Mg',
        'Zn-Ga',
        'Zn-Kr',
        'Ga-Xe',
    ]:
        assert mixed_core_correlation_assert(range)

    for range in [
        'Kr-Ga',
    ]:
        assert not mixed_core_correlation_assert(range)
        assert not mixed_core_correlation_assert(range, False)

    for range in [
        'bad',
        'bad-worse',
        4.0,
        {'a':'b'},
        True,
    ]:
        with pytest.raises(ValueError):
            mixed_core_correlation_assert(range)
