import glob
import logging
import os
from dataclasses import dataclass

import lxml
from pymolpro import Project as BaseProject

from .utilities import MOLPRO_XML_NAMESPACES, VibrationSetXML, atoms_from_atom_array_node

logger = logging.getLogger(__name__)

# Pseudo-suffix for filename(): the output file written by a Slurm batch job. Slurm's naming
# isn't known to sjef, so unlike the other suffixes it can't be looked up via the normal
# suffix->filename mapping and has to be found by globbing the run directory instead.
SLURM_OUTPUT_SUFFIX = 'slurm_out'


@dataclass
class Structure:
    atoms: list[dict]
    vibrations: VibrationSetXML = None

    def __str__(self):
        return 'atoms: ' + str(self.atoms) + '\nvibrations: ' + str(self.vibrations)


class Project(BaseProject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def filename(self, suffix="", name="", run=0):
        if type(self.run_directory) != int:
            raise Exception('run_directory must be an integer ' + str(self.run_directory))
        # print('filename', suffix, 'name=',name, 'run=', run, 'self.run_directory=',self.run_directory)
        run = self.run_directory if run == 0 else run
        if suffix == SLURM_OUTPUT_SUFFIX and not name:
            return self._slurm_output_filename(run)
        filename = super().filename(suffix, name, run)
        # print('evaluated filename',filename)
        return filename

    def _slurm_output_filename(self, run) -> str:
        """
        Find the file written by a Slurm batch job's output redirection for the given run, if
        any. Its name is controlled by the user's own job-submission script, not by sjef or
        iMolpro, so the only thing that can be assumed about it is that it contains 'slurm'
        somewhere in the name (including the suffix). If the project's own name also contains
        'slurm', that alone isn't enough to tell a real Slurm output file apart from any other
        run-directory file that happens to start with the project name, so in that case require
        'slurm' to appear twice.
        """
        run_directory = os.path.dirname(super().filename('out', '', run))
        minimum_occurrences = 2 if 'slurm' in self.name else 1
        matches = [
            f for f in glob.glob(os.path.join(run_directory, '*slurm*'))
            if os.path.isfile(f) and os.path.basename(f).count('slurm') >= minimum_occurrences
        ]
        return max(matches, key=os.path.getmtime) if matches else ''

    @property
    def run_directory_names(self) -> list[str]:
        result = []
        dirs = self.property_get('run_directories')
        if dirs and 'run_directories' in dirs:
            result = [''] + dirs['run_directories'].strip().split(' ')
        return result

    def structure(self, require_frequencies=False, run=0, instance=-1) -> Structure:
        r'''
        Get a structure of the molecule from the output. If require_frequencies is True, the
        returned Structure's vibrations attribute is populated when the output has associated
        vibrational frequency data; otherwise (including when require_frequencies is True but no
        frequency data is present) a plain-geometry Structure with vibrations=None is returned.
        :param require_frequencies: If True, populate vibrational frequency data when available
        :param run: The run number for which the output will be analysed.
        :param instance: The instance number in the output of the geometry. If negative, count from the end.
        :return: The structure of the molecule
        '''
        namespaces_ = MOLPRO_XML_NAMESPACES
        if not self.xml:
            return None
        with open(self.filename('xml', run=run), 'r') as f:
            xml = f.read()
        try:
            root = lxml.etree.fromstring(xml)
        except lxml.etree.XMLSyntaxError:
            # Molpro is still writing this run's XML output -- it's systematically incomplete
            # (missing its closing tags) until the job finishes, so this is expected and can
            # happen on every refresh tick while a job is running, not an error.
            return None

        vibrations = None
        if require_frequencies:
            try:
                # Reparses xml itself rather than accepting the already-parsed root above, but
                # since that parse just succeeded on this exact content, this one won't fail
                # with XMLSyntaxError -- only with a real "no frequency data here" reason (eg
                # IndexError, no <vibrations> element in a non-FREQ job's output), which the
                # broad except below is for.
                vibrations = VibrationSetXML(xml, instance=instance)
            except Exception:
                logger.debug('No vibrational frequency data available for %s (run=%s, instance=%s)',
                             self.filename('xml', run=run), run, instance, exc_info=True)
        if vibrations:
            return Structure(vibrations.atoms, vibrations)
        else:
            coords = root.xpath('(//cml:atomArray)', namespaces=namespaces_)
            return Structure(atoms_from_atom_array_node(coords[instance]))


if __name__ == '__main__':
    p = Project(geometry='F;H,F,1.7', method='hf', job_type='OPT+FREQ')
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
    print(p.structure(True, instance=-1))
    print(p.structure(False))
    print(p.structure(False, instance=0))
