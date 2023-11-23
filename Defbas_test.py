import os.path
import pathlib

import pymolpro
import pytest

from defbas import Defbas


def test_content(qtbot, tmpdir):
    p = pymolpro.Project(str(tmpdir / 'test.molpro'))
    defbas = Defbas(p.local_molpro_root())
    if defbas is not None:
        assert defbas.contents

    assert len(defbas.search('Ne', 'vdz')) == 1
    with pytest.raises(ValueError):
        defbas.search('bad', 'vdz')
    assert len(defbas.search('Ne', 'bad')) == 0
    assert defbas.search('Ne', 'aug-cc-pVTZ')[0]['maxang'] == 3
