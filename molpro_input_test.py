from molpro_input import parse, create_input, basis_quality
import time


def test_file(qtbot, tmpdir):
    test_file = tmpdir / 'test-molpro_input.inp'
    test_text = 'Geometry={F;H,F,1.7};geometry=hf.xyz;basis=cc-pVTZ !some comment;rhf\nccsd\n'
    with open(test_file, 'w') as f:
        f.write(test_text)
    assert parse(test_text) == parse(test_file)


def test_create_input(qtbot):
    for test_text in [
        'Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF;H,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF\nH,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
    ]:
        # print('test_text',test_text)
        specification = parse(test_text)
        # print('specification',specification)
        # print(create_input(specification))
        assert parse(create_input(specification)) == specification


def test_variables(qtbot):
    test_text = 'spin=2,charge=1! comment\nset,occ=[3,1,1] ! comments\n;Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment\n{ks,b3lyp};locali\nccsd\n'
    specification = parse(test_text)
    # print('original input', test_text)
    # print('parsed specification', specification)
    # print('recreated input', create_input(specification))
    assert parse(create_input(specification)) == specification
    assert specification['variables']['spin'] == '2'
    assert specification['variables']['occ'] == '[3,1,1]'


def test_too_complex(qtbot):
    for test_text in [
        'geometry=a.xyz;geometry=b.xyz',
        'geometry=b.xyz;hf;ccsd;hf',
        'geometry=c.xyz;hf;basis=cc-pvtz;ccsd',
    ]:
        assert parse(test_text) == {}


def test_basis_qualities(qtbot):
    for test, quality in {
        'basis=cc-pVDZ': 2,
        'basis={default=cc-pVDZ}': 2,
        'basis={default=cc-pVDZ,H=cc-pVDZ}': 2,
        'basis={default=cc-pVTZ,H=cc-pVDZ}': 0,
    }.items():
        assert basis_quality(parse(test)) == quality
