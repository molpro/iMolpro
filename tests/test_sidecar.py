import os
import pathlib

import pytest

from iMolpro.project import Project, sidecar_files, with_sidecar_files

XML_TEMPLATE = '''<?xml version="1.0"?>
<molpro xmlns="http://www.molpro.net/schema/molpro-output">
 <job>
  <jobstep command="RHF-SCF">
   <molecule id="M1">
    {orbitals}
   </molecule>
  </jobstep>
 </job>
</molpro>
'''


def _write_xml(path: pathlib.Path, *sidecars):
    orbitals = ''.join(f'<orbitals sidecar="{s}" method="RHF" type="CANONICAL">'
                       f'<orbital ID="1.1" occupation="2.0" sidecar_offset="0"/></orbitals>' for s in sidecars)
    path.write_text(XML_TEMPLATE.format(orbitals=orbitals))
    return path


def test_sidecar_files_finds_referenced_existing_files(tmp_path):
    xml = _write_xml(tmp_path / 'job.xml', 'job.xml-sidecar', 'job.xml-sidecar', 'other-sidecar', 'missing-sidecar')
    (tmp_path / 'job.xml-sidecar').write_bytes(b'\0')
    (tmp_path / 'other-sidecar').write_bytes(b'\0')
    assert sidecar_files(xml) == [str(tmp_path / 'job.xml-sidecar'), str(tmp_path / 'other-sidecar')]


def test_sidecar_files_ignores_paths_with_directories(tmp_path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 's').write_bytes(b'\0')
    (tmp_path / 's').write_bytes(b'\0')
    xml = _write_xml(tmp_path / 'job.xml', 'sub/s', '../s', '')
    assert sidecar_files(xml) == []


def test_sidecar_files_without_sidecar_or_invalid_xml(tmp_path):
    assert sidecar_files(_write_xml(tmp_path / 'plain.xml')) == []
    bad = tmp_path / 'bad.xml'
    bad.write_text('not xml <')
    assert sidecar_files(bad) == []
    assert sidecar_files(tmp_path / 'absent.xml') == []


def test_with_sidecar_files_keeps_order_and_skips_non_xml(tmp_path):
    xml = _write_xml(tmp_path / 'job.xml', 'job.xml-sidecar')
    sidecar = tmp_path / 'job.xml-sidecar'
    sidecar.write_bytes(b'\0')
    out = tmp_path / 'job.out'
    out.write_text('')
    assert with_sidecar_files([str(xml), str(out)]) == [str(xml), str(out), str(sidecar)]
    assert with_sidecar_files([str(xml), str(sidecar)]) == [str(xml), str(sidecar)]
    assert with_sidecar_files([str(out), 'https://example.com/x.xml']) == [str(out), 'https://example.com/x.xml']


def test_project_from_xml_gets_sidecar_next_to_output(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    xml = _write_xml(source / 'job.xml', 'job.xml-sidecar')
    (source / 'job.xml-sidecar').write_bytes(b'sidecar-data')
    (tmp_path / 'projects').mkdir()
    project = Project(location=str(tmp_path / 'projects'), files=with_sidecar_files([str(xml)]))
    copied = pathlib.Path(project.filename('xml')).parent / 'job.xml-sidecar'
    assert copied.read_bytes() == b'sidecar-data'


SANDBOX_XML = pathlib.Path(__file__).parent.parent / 'sandbox' / 'mpr_pentacene_dfrhf_vtz_sym.299190-20261005.xml'


@pytest.mark.skipif(not SANDBOX_XML.is_file(), reason='sandbox example with sidecar not present')
def test_orbitals_readable_from_real_sidecar_output(tmp_path):
    project = Project(location=str(tmp_path), files=with_sidecar_files([str(SANDBOX_XML)]))
    orbitals = project.orbitals(0)
    assert len(orbitals) == 73
    assert all(len(orbital.coefficients) == 980 for orbital in orbitals)
