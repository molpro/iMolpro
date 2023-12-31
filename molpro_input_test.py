from molpro_input import parse, create_input, basis_quality, equivalent, canonicalise
import time

allowed_methods_ = ['RHF', 'CCSD', 'RKS', 'CASSCF', 'MRCI']


def test_file(qtbot, tmpdir):
    test_file = tmpdir / 'test-molpro_input.inp'
    test_text = 'Geometry={F;H,F,1.7};geometry=hf.xyz;basis=cc-pVTZ !some comment;rhf\nccsd\n'
    with open(test_file, 'w') as f:
        f.write(test_text)
    assert parse(test_text, allowed_methods=allowed_methods_) == parse(test_file, allowed_methods=allowed_methods_)


def test_create_input(qtbot):
    for specification in [
        {'job_type': 'Single Point Energy', 'geometry': 'F\nH,F,1.7\n',
         'basis': {'default': 'cc-pVTZ', 'elements': {}, 'quality': 3},
         'precursor_methods': ['{rks,b3lyp}'], 'method': 'ccsd', 'hamiltonian': 'AE', 'method_options': []},
        {'job_type': 'Single Point Energy', 'geometry': 'F\nH,F,1.7\n',
         'basis': {'default': 'cc-pVTZ', 'elements': {}, 'quality': 3},
         'precursor_methods': [], 'method': 'rks', 'density_functional': 'b3lyp', 'hamiltonian': 'AE', 'method_options': []},
        {'job_type': 'Single Point Energy', 'geometry': 'F\nH,F,1.7\n',
         'basis': {'default': 'cc-pVTZ', 'elements': {}, 'quality': 3},
         'precursor_methods': [], 'method': 'rhf', 'hamiltonian': 'AE', 'method_options': ['b3lyp','opt1=val1','','opt2=val2','','opt3']},
    ]:
        # print(create_input(specification))
        # print('new_specification', parse(create_input(specification), allowed_methods=allowed_methods_))
        assert parse(create_input(specification), allowed_methods=allowed_methods_) == specification

    for test_text in [
        'Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF;H,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'Geometry={\nF\nH,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};locali\nccsd\n',
        'geometry={\nHe\n}\nhf',
        'geometry={\nHe\n}\nhf\nccsd',
        'geometry=thing.xyz',
        'geometry={H};uhf',
        'geometry={H};{uhf}',
        'geometry={H};{rhf}',
        'geometry={H};{hf}',
        'geometry={H};{uks,b3lyp};ccsd',
        'geometry={H};{rks,b3lyp};ccsd',
        'geometry={H};{ks,b3lyp};ccsd',
        'geometry={H};uks,b3lyp;ccsd',
        'geometry={H};uks,b3lyp',
        'geometry={H};rks,b3lyp',
        'geometry={H};ks,b3lyp',
        'geometry={H};ks,b3lyp,option1,,option2,,',
    ]:
        # print('test_text', test_text)
        specification = parse(test_text, allowed_methods=allowed_methods_)
        # print('specification', specification)
        # print(create_input(specification))
        assert parse(create_input(specification), allowed_methods=allowed_methods_) == specification


def test_recreate_input(qtbot):
    for test_text in [
        'geometry={\nHe\n}\nhf',
        'geometry={\nHe\n}\nhf\nccsd',
        'geometry={\nHe\n}\nhf\nccsd\n\n',
        'geometry={He}\nhf\nccsd\n\n',
        '\ngeometry={\nB\nH B 2.2\n}\nocc,5,1,1,context=mcscf\nrhf\ncasscf\nmrci',
        'geometry={He};rks,b3lyp',
        'geometry={He};{rks,b3lyp}',
        'geometry=newnewnew.xyz\nbasis=cc-pVTZ-PP\nrhf',
        'geometry=wed.xyz\nbasis=cc-pVTZ-PP\nset,charge=1,spin=1,thing=whatsit\nxx=yy,p=q\nrhf',
    ]:
        # print('test_text',test_text)
        specification = parse(test_text, allowed_methods=allowed_methods_)
        # print('specification',specification)
        # print(create_input(specification))
        assert parse(create_input(specification), allowed_methods=allowed_methods_) == specification
        assert equivalent(specification, test_text, debug=False)


def test_variables(qtbot):
    test_text = 'spin=2,charge=1! comment\nset,occ=[3,1,1] ! comments\n;Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ}\n{ks,b3lyp}!some comment;locali\nccsd\n'
    specification = parse(test_text, allowed_methods=allowed_methods_)
    # print('original input', test_text)
    # print('parsed specification', specification)
    # print('recreated input', create_input(specification))
    # print('parsed recreated input', parse(create_input(specification), allowed_methods=allowed_methods_))
    assert parse(create_input(specification), allowed_methods=allowed_methods_) == specification
    assert specification['variables']['spin'] == '2'
    assert specification['variables']['occ'] == '[3,1,1]'


def test_too_complex(qtbot):
    for test_text in [
        'geometry=a.xyz;geometry=b.xyz',
        'geometry=b.xyz;hf;ccsd;hf',
        'geometry=c.xyz;hf;basis=cc-pvtz;ccsd',
    ]:
        assert parse(test_text, allowed_methods=allowed_methods_) == {}


def test_canonicalise(qtbot):
    for given, expected in {
        'geometry={\nHe\n}': 'geometry={He}\n',
        'a\n\n\nb\n': 'a\nb\n',
        'basis={\ndefault=cc-pVTZ,h=cc-pVDZ\n} !some comment': 'basis={default=cc-pVTZ,h=cc-pVDZ} !some comment\n'
    }.items():
        assert canonicalise(given) == expected
    for test_text in [
        'geometry={He}',
    ]:
        assert equivalent(test_text, create_input(parse(test_text, allowed_methods=allowed_methods_)))


def test_basis_qualities(qtbot):
    for test, quality in {
        'basis=cc-pVDZ': 2,
        'basis={default=cc-pVDZ}': 2,
        'basis={default=cc-pVDZ,H=cc-pVDZ}': 2,
        'basis={default=cc-pVTZ,H=cc-pVDZ}': 0,
    }.items():
        assert basis_quality(parse(test, allowed_methods=allowed_methods_)) == quality
        assert parse(test, allowed_methods=allowed_methods_)['basis']['quality'] == quality


def test_basis_variants(qtbot):
    for test, outcome in {
        'basis=cc-pVDZ': 'basis=cc-pVDZ',
        'basis,cc-pVDZ': 'basis=cc-pVDZ',
        'basis=default=cc-pVDZ': 'basis=cc-pVDZ',
        'basis={default=cc-pVDZ}': 'basis=cc-pVDZ',
        'basis={cc-pVDZ}': 'basis=cc-pVDZ',
        'basis,default=cc-pVDZ': 'basis=cc-pVDZ',
        'basis,cc-pVDZ,h=cc-pVDZ(s)': 'basis=cc-pVDZ,H=cc-pVDZ(s)',
        'basis,cc-pVDZ,zR=cc-pVDZ(s),h=cc-pVTZ': 'basis=cc-pVDZ,Zr=cc-pVDZ(s),H=cc-pVTZ',
        'basis={cc-pVDZ,zR=cc-pVDZ(s),h=cc-pVTZ}': 'basis=cc-pVDZ,Zr=cc-pVDZ(s),H=cc-pVTZ',
    }.items():
        assert create_input(parse(test)) == outcome.strip('\n') + '\n'
