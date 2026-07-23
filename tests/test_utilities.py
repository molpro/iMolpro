import json
import os

import pytest

from iMolpro.utilities import FileBackedDictionary


@pytest.fixture
def dict_file(tmp_path):
    return str(tmp_path / 'nested' / 'dictionary.json')


def test_basic_mapping_operations(dict_file):
    d = FileBackedDictionary(dict_file)
    assert len(d) == 0
    assert list(d) == []

    d['a'] = 1
    d['b'] = 2
    assert d['a'] == 1
    assert d['b'] == 2
    assert len(d) == 2
    assert set(d) == {'a', 'b'}
    assert 'a' in d
    assert 'z' not in d

    del d['a']
    assert 'a' not in d
    assert len(d) == 1

    with pytest.raises(KeyError):
        d['a']


def test_persistence_to_file_and_reload(dict_file):
    d = FileBackedDictionary(dict_file)
    d['a'] = 1
    d['b'] = 'text'

    assert os.path.isfile(dict_file)
    with open(dict_file, 'r') as f:
        assert json.load(f) == {'a': 1, 'b': 'text'}

    reloaded = FileBackedDictionary(dict_file)
    assert dict(reloaded) == {'a': 1, 'b': 'text'}


def test_external_file_change_is_picked_up(dict_file):
    d = FileBackedDictionary(dict_file)
    d['a'] = 1

    import time
    time.sleep(0.01)  # ensure a distinguishable mtime
    with open(dict_file, 'w') as f:
        json.dump({'a': 99, 'c': 3}, f)

    assert d['a'] == 99
    assert d['c'] == 3


def test_default_value_used_when_key_not_set(dict_file):
    d = FileBackedDictionary(dict_file)
    d.add_default('colour', 'red')

    assert d['colour'] == 'red'
    # the default must not be persisted, nor counted as a stored key
    assert 'colour' not in list(d)
    assert len(d) == 0
    # nothing was ever explicitly set, so no file should have been written
    assert not os.path.exists(dict_file)


def test_explicit_value_overrides_default(dict_file):
    d = FileBackedDictionary(dict_file)
    d.add_default('colour', 'red')

    d['colour'] = 'blue'
    assert d['colour'] == 'blue'
    with open(dict_file, 'r') as f:
        assert json.load(f) == {'colour': 'blue'}


def test_setting_default_sentinel_reverts_to_default(dict_file):
    d = FileBackedDictionary(dict_file)
    d.add_default('colour', 'red')

    d['colour'] = 'blue'
    assert d['colour'] == 'blue'

    d['colour'] = FileBackedDictionary.DEFAULT
    assert d['colour'] == 'red'
    with open(dict_file, 'r') as f:
        assert json.load(f) == {}


def test_default_sentinel_on_unset_key_is_a_noop(dict_file):
    d = FileBackedDictionary(dict_file)
    d.add_default('colour', 'red')

    d['colour'] = FileBackedDictionary.DEFAULT  # never explicitly set
    assert d['colour'] == 'red'
    # no stored value was ever removed, so no file should have been written
    assert not os.path.exists(dict_file)


def test_missing_key_without_default_raises(dict_file):
    d = FileBackedDictionary(dict_file)
    with pytest.raises(KeyError):
        d['nonexistent']
