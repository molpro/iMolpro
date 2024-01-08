from molpro_input import equivalent, canonicalise, InputSpecification, supported_methods
import pytest

@pytest.fixture
def methods():
    import molpro_input
    molpro_input.supported_methods = ['RHF', 'CCSD', 'RKS', 'CASSCF', 'MRCI','UHF','UKS','OCC','OPTG','FREQUENCIES','THERMO']
    yield supported_methods



def test_file(methods, tmpdir):
    test_file = tmpdir / 'test-molpro_input.inp'
    test_text = 'Geometry={F;H,F,1.7};geometry=hf.xyz;basis=cc-pVTZ !some comment;rhf\nccsd\n'
    with open(test_file, 'w') as f:
        f.write(test_text)
    assert InputSpecification(test_text) == InputSpecification(test_file)


def test_create_input(methods):
    for spec in [
        {'geometry': 'F\nH,F,1.7',
         'basis': {'default': 'cc-pVTZ', 'elements': {}},
         'steps': [{'command': 'rks', 'density_functional': 'b3lyp'}, {'command': 'ccsd'}],
            'hamiltonian':'AE',
         },
    ]:
        specification = InputSpecification(specification=spec)

        # print('initial specification',specification)
        # print('created input',specification.create_input(),'---')
        # print('new_specification', InputSpecification(specification.create_input()))
        assert InputSpecification(specification.create_input()) == specification

    for input in [
        'Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};{ccsd}\n',
        'Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};ccsd\n',
        'Geometry={\nF;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};ccsd\n',
        'Geometry={\nF;H,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};ccsd\n',
        'Geometry={\nF\nH,F,1.7\n};basis={default=cc-pVTZ,h=cc-pVDZ} !some comment;{ks,b3lyp};ccsd\n',
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
        'geometry={H};ccsd,option1,option2=thing,,',
        'geometry={H};ks,b3lyp,option1,option2,,',
    ]:
        # print('new one---\n',input)
        specification = InputSpecification(input)
        regenerated_input = specification.create_input()
        regenerated_specification = InputSpecification(regenerated_input)
        assert regenerated_specification == specification
        if not equivalent(regenerated_input , input):
            print('input', input)
            print('specification', specification)
            print('regenerated_specification', regenerated_specification)
            print('regenerated_input', regenerated_input)
            canonicalised_input = canonicalise(input)
            print('canonicalised input', canonicalised_input, type(canonicalised_input))
            canonicalised_regenerated_input = canonicalise(regenerated_input)
            print('canonicalised regenerated_input', canonicalised_regenerated_input,type(canonicalised_regenerated_input))
            assert canonicalised_input == canonicalised_regenerated_input


def test_recreate_input(methods):
    for input in [
        'geometry={\nHe\n}\nhf',
        'geometry={\nHe\n}\nhf\nccsd',
        'geometry={\nHe\n}\nhf\nccsd\n\n',
        'geometry={He}\nhf\nccsd\n\n',
        # '\ngeometry={\nB\nH B 2.2\n}\nocc,5,1,1,context=mcscf\nrhf\ncasscf\nmrci', #TODO make options positional list
        'geometry={He};rks,b3lyp',
        'geometry={He};{rks,b3lyp}',
        'geometry=newnewnew.xyz\nbasis=cc-pVTZ-PP\nrhf',
        'geometry=wed.xyz\nbasis=cc-pVTZ-PP\nset,charge=1,spin=1,thing=whatsit\nxx=yy,p=q\nrhf',
        'geometry={Ne};{rhf};ccsd;{frequencies;thermo,temp=298;another}',
    ]:
        specification = InputSpecification(input)
        regenerated_input = specification.create_input()
        regenerated_specification = InputSpecification(regenerated_input)
        if not equivalent(regenerated_input, input) or regenerated_specification != specification:
            print('specification', specification)
            print('regenerated_specification', regenerated_specification)
            print('input', input)
            print('regenerated_input', regenerated_input)
            print('canonicalised input', canonicalise(input))
            print('canonicalised regenerated_input', canonicalise(regenerated_input))
        assert canonicalise(regenerated_input) == canonicalise(input)
        assert regenerated_specification == specification


def test_variables(methods):
    test_text = 'spin=2,charge=1! comment\nset,occ=[3,1,1] ! comments\n;Geometry={F;H,F,1.7};basis={default=cc-pVTZ,h=cc-pVDZ}\n{ks,b3lyp}!some comment;ccsd\n'
    specification = InputSpecification(test_text)
    # print('original input', test_text)
    # print('parsed specification', specification)
    # print('recreated input', create_input(specification))
    # print('parsed recreated input', InputSpecification(create_input(specification)))
    assert InputSpecification(specification.create_input()) == specification
    assert specification['variables']['spin'] == '2'
    assert specification['variables']['occ'] == '[3,1,1]'


def test_too_complex(methods):
    for test_text in [
        # 'geometry=a.xyz;geometry=b.xyz',
        # 'geometry=b.xyz;hf;ccsd;hf',
        'geometry=c.xyz;hf;basis=cc-pvtz;ccsd',
    ]:
        assert InputSpecification(test_text) == {}


def test_canonicalise(methods):
    for given, expected in {
        'geometry={\nHe\n}': 'geometry={he}\n',
        'a\n\n\nb\n': '{a}\n{b}\n',
        # 'basis={\ndefault=cc-pVTZ,h=cc-pVDZ\n} !some comment': 'basis=cc-pvtz,h=cc-pvdz !some comment\n'
        'basis={\ndefault=cc-pVTZ,h=cc-pVDZ\n} !some comment': 'basis=cc-pvtz,h=cc-pvdz\n'
    }.items():
        assert canonicalise(given) == expected
    for test_text in [
        'geometry={He}',
    ]:
        assert equivalent(test_text, InputSpecification(test_text).create_input())


def test_basis_qualities(methods):
    for test, quality in {
        'basis=cc-pVDZ': 2,
        'basis={default=cc-pVDZ}': 2,
        'basis={default=cc-pVDZ,H=cc-pVDZ}': 2,
        'basis={default=cc-pVTZ,H=cc-pVDZ}': 0,
    }.items():
        assert InputSpecification(test).basis_quality == quality


def test_basis_variants(methods):
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
        assert InputSpecification(test).create_input() == outcome.strip('\n') + '\n'
