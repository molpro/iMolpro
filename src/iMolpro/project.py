from dataclasses import dataclass

import lxml
from pymolpro import Project as BaseProject
from pymolpro.defbas import periodic_table

from .utilities import VibrationSetXML



@dataclass
class Structure:
    atoms: list[dict]
    vibrations: VibrationSetXML = None

    def __str__(self):
        return 'atoms: '+str(self.atoms)+'\nvibrations: '+str(self.vibrations)


class Project(BaseProject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def filename(self, suffix="", name="", run=0):
        if type(self.run_directory) != int:
            raise Exception('run_directory must be an integer ' + str(self.run_directory))
        # print('filename', suffix, 'name=',name, 'run=', run, 'self.run_directory=',self.run_directory)
        filename = super().filename(suffix, name, self.run_directory if run == 0 else run)
        # print('evaluated filename',filename)
        return filename

    @property
    def run_directory_names(self) -> list[str]:
        result = []
        dirs = self.property_get('run_directories')
        if dirs and 'run_directories' in dirs:
            result = [''] + dirs['run_directories'].strip().split(' ')
        return result

    def structure(self, require_frequencies=False, run=0, instance=-1) -> Structure:
        r'''
        Get a structure of the molecule from the output. If require_frequencies is True, then only return a structure if it has frequencies.
        :param require_frequencies: If True, consider only structures that have associated vibrational frequencies
        :param run: The run number for which the output will be analysed.
        :param instance: The instance number in the output of the geometry. If negative, count from the end.
        :return: The structure of the molecule
        '''
        namespaces_ = {'molpro-output': 'http://www.molpro.net/schema/molpro-output',
                       'xsd': 'http://www.w3.org/1999/XMLSchema',
                       'cml': 'http://www.xml-cml.org/schema',
                       'stm': 'http://www.xml-cml.org/schema',
                       'xhtml': 'http://www.w3.org/1999/xhtml'}
        if not self.xml:
            return None
        with open(self.filename('xml', run=run),'r') as f:
            xml = f.read()

        if require_frequencies:
            try:
                vibrations = VibrationSetXML(xml, instance=instance)
            except:
                vibrations = None
        if vibrations:
            return Structure(vibrations.atoms, vibrations)
        else:
            root = lxml.etree.fromstring(xml)
            coords = root.xpath('(/*/*/*/*/cml:atomArray)', namespaces=namespaces_)
            atoms=[]
            angstrom = 1.8897161646321
            for coord in coords[instance]:
                atoms.append({'xyz': [angstrom*float(coord.attrib['x3']),angstrom*float(coord.attrib['y3']),angstrom*float(coord.attrib['z3'])],'atomic_number':periodic_table.index(coord.attrib['elementType'])+1})
            return Structure(atoms)

if __name__ == '__main__':
    p = Project(geometry='F;H,F,1.7',method='hf',job_type='OPT+FREQ')
    p = Project()
    p.write_input('geometry={F;H,F,1.7};df-hf;optg;freq;df-hf;df-mp2;optg;freq')
    p.run(wait=True)
    # print(p.out)
    # print(p.xml)
    # print(VibrationSetXML(p.xml))
    # print(VibrationSetXML(p.xml,instance=0))
    # print(VibrationSetXML(p.xml,instance=1))
    # print(VibrationSetXML(p.xml,instance=-1))
    # print(VibrationSetXML(p.xml,instance=-2))
    print(p.structure(True))
    # print(p.structure(True).vibrations)
    print(p.structure(True,instance=-1))
    print(p.structure(False))
    print(p.structure(False,instance=0))
