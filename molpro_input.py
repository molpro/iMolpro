import os
import pathlib
import re
from collections import UserDict

wave_fct_symm_commands = {
    'Automatic': '',
    'No Symmetry': 'symmetry,nosym'
}
wave_fct_symm_aliases = {
    'nosym': 'symmetry,nosym',
}

hamiltonians = {
    'AE': {'text': 'All Electron', 'basis_string': ''},
    'PP': {'text': 'Pseudopotential', 'basis_string': '-PP'},
    'DK': {'text': 'Douglas-Kroll-Hess', 'basis_string': '-DK'},
    'DK3': {'text': 'Douglas-Kroll-Hess 3', 'basis_string': '-DK3'},
}

orbital_types = {
    'canonical': {'text': 'Canonical', 'command': ''},
    'ibo': {'text': 'Intrinsic Bond', 'command': 'ibba'},
    'pipek': {'text': 'Pipek-Mezey', 'command': 'locali,pipek'},
    'nbo': {'text': 'NBO', 'command': 'nbo'},
    'boys': {'text': 'Boys', 'command': 'locali'},
}

parameter_commands = {
    'parameters': 'gparam',
    'thresholds': 'gthresh',
    'prints': 'gprint',
}

job_type_steps = {
    'Single point energy': [],
    'Geometry optimisation': [{'command': 'optg', 'options': ['savexyz=optimised.xyz']}],
    'Hessian': [{'command': 'frequencies', 'directives': [{'command': 'thermo'}]}],
}
job_type_steps['Optimise + vib frequencies'] = job_type_steps['Geometry optimisation'] + job_type_steps['Hessian']
job_type_aliases = {
    '{optg}': 'optg',
    '{freq}': 'frequencies',
    'freq': 'frequencies',
}
orientation_options = {
    'Mass': 'mass',
    'Charge': 'charge',
    'None': 'noorient'
}

properties = {
    'Dipole moment': 'gexpec,dm',
    'Quadrupole moment': 'gexpec,qm',
    'Second moment': 'gexpec,sm',
    'Kinetic energy': 'gexpec,ekin',
    'Cowan-Griffin': 'gexpec,rel',
    'Mass-velocity': 'gexpec,massv',
    'Darwin': 'gexpec,darw',
}

initial_orbital_methods = ['HF', 'KS']

supported_methods = []


class InputSpecification(UserDict):
    hartree_fock_methods = ['RHF', 'RKS', 'UHF', 'UKS', 'LDF-RHF', 'LDF-UHF']

    def __init__(self, input=None, allowed_methods=[], debug=False, specification=None, directory=None):
        super(InputSpecification, self).__init__()
        self.allowed_methods = list(set(allowed_methods).union(set(supported_methods)))
        self.directory = directory
        # print('self.allowed_methods',self.allowed_methods)
        self.debug = debug
        if specification is not None:
            for k in specification:
                self[k] = specification[k]
        if input is not None:
            self.parse(input)
        if 'hamiltonian' not in self and self.data:
            self['hamiltonian'] = 'PP'

    def parse(self, input: str, debug=False):
        r"""
        Take a molpro input, and logically parse it

        :param input: Either text that is the input, or a file name containing it.
        :return:
        :rtype: InputSpecification
        """
        if os.path.exists(input):
            with open(input, 'r') as f:
                print(input)
                return self.parse(f.read())

        # print('allowed_methods', self.allowed_methods)
        precursor_methods = ['LOCALI', 'CASSCF', 'OCC', 'CORE', 'CLOSED', 'FROZEN', 'WF',
                             'LOCAL', 'DFIT',
                             'DIRECT', 'EXPLICIT', 'THRESH', 'GTHRESH', 'PRINT', 'GRID']
        df_prefixes = ['', 'DF-']
        postscripts = ['PUT', 'TABLE', 'NOORBITALS', 'NOBASIS']  # FIXME not very satisfactory

        self.clear()
        variables = {}
        geometry_active = False
        self['steps'] = []
        canonicalised_input_ = re.sub('basis\n(.*)\n *end', r'basis={\1}', input,
                                      flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
        canonicalised_input_ = re.sub('basis={\n', r'basis={', canonicalised_input_,
                                      flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
        old_input_ = ''
        count = 100
        while (canonicalised_input_ != old_input_ and count):
            count -= 1
            old_input_ = canonicalised_input_
            canonicalised_input_ = re.sub('basis={([^}]+[^,}])\n([^}]+=[^}]+)}', r'basis={\1,\2}', canonicalised_input_,
                                          flags=re.DOTALL | re.IGNORECASE)
        if not re.match('.*basis={ *s[pdfghi]* *[,}].*', canonicalised_input_, flags=re.DOTALL | re.IGNORECASE):
            canonicalised_input_ = re.sub('basis={ *([^}]*)\n*}', r'basis, \1', canonicalised_input_,
                                          flags=re.DOTALL | re.IGNORECASE)
        canonicalised_input_ = canonicalised_input_.replace('{FREQ}', '{frequencies\nthermo}')  # hack for gmolpro

        # parse and protect {....}
        line_end_protected_ = '±'
        for i in range(len(canonicalised_input_)):
            if canonicalised_input_[i] == '{':
                for j in range(i + 1, len(canonicalised_input_)):
                    if canonicalised_input_[j] == '}':
                        canonicalised_input_ = canonicalised_input_[:j] + '}\n' + canonicalised_input_[j + 1:];
                        break
                    elif canonicalised_input_[j] in ';\n':
                        canonicalised_input_ = canonicalised_input_[:j] + line_end_protected_ + canonicalised_input_[
                                                                                                j + 1:]
        canonicalised_input_ = canonicalised_input_.replace(';', '\n').replace(line_end_protected_, ';')
        for line in canonicalised_input_.split('\n'):
            line = re.sub('basis *,', 'basis=', line, flags=re.IGNORECASE)
            group = line.strip()
            if not re.match('.*basis={ *s[pdfghi]* *[,}].*', line, flags=re.DOTALL | re.IGNORECASE):
                line = group.split(line_end_protected_)[0].replace('{', '').strip()
            command = re.sub('[;, !].*$', '', line, flags=re.IGNORECASE).replace('}', '').lower()
            for df_prefix in df_prefixes:
                if command == df_prefix.lower() + 'hf': command = df_prefix.lower() + 'rhf'
                if command == df_prefix.lower() + 'ks': command = df_prefix.lower() + 'rks'
                if command == df_prefix.lower() + 'ldf-ks': command = df_prefix.lower() + 'ldf-rks'
            # print('command', command,'line',line,'group',group)
            for m in initial_orbital_methods:
                if m.lower() in command.lower() and not any([s + m.lower() in command.lower() for s in ['r', 'u']]):
                    loc = command.lower().index(m.lower())
                    command = re.sub(m.lower(), 'r' + m.lower(), command, flags=re.IGNORECASE)
                    line = re.sub(m.lower(), 'r' + m.lower(), line, flags=re.IGNORECASE)
            if re.match('^orient *, *', line, re.IGNORECASE):
                line = re.sub('^orient *, *', '', line, flags=re.IGNORECASE)
                for orientation_option in orientation_options.keys():
                    if (line.lower() == orientation_options[orientation_option].lower()):
                        self['orientation'] = orientation_option
                        break
            elif ((command.lower() == 'nosym') or (re.match('^symmetry *, *', line, re.IGNORECASE))):
                line = re.sub('^symmetry *, *', '', line, flags=re.IGNORECASE)
                line = "symmetry," + line
                for symmetry_command in wave_fct_symm_commands.keys():
                    if (line.lower() == wave_fct_symm_commands[symmetry_command]):
                        self['wave_fct_symm'] = symmetry_command
                        break
            elif re.match('^dkho *=.*', command, re.IGNORECASE):
                self['hamiltonian'] = re.sub('^dkho *= *', 'DK', command, flags=re.IGNORECASE).replace('DK1', 'DK')
            elif line.lower() in properties.values():
                if 'properties' not in self: self['properties'] = []
                self['properties'] += [k for k, v in properties.items() if line.lower() == v]
            # elif any([line.lower() == v['command'].lower() for v in orbital_types.values()]):
            #     last_orbital_generator = [k for k, v in orbital_types.items() if command.lower() == v['command'].lower()]
            elif any([re.match('put,molden,' + k + '.molden', line, flags=re.IGNORECASE) for k in
                      orbital_types.keys()]):
                if 'orbitals' not in self: self['orbitals'] = []
                for k in orbital_types:
                    if re.match('put,molden,' + k + '.molden', line, flags=re.IGNORECASE):
                        self['orbitals'].append(k)
            elif re.match('^geometry *= *{', group, re.IGNORECASE):
                # print('geometry matched')
                if 'steps' in self and self['steps']: self.data.clear(); return self  # input too complex
                if 'geometry' in self: self.data.clear(); return self  # input too complex
                self['geometry'] = re.sub(';', '\n',
                                          re.sub('^geometry *= *{ *\n*', '', group + '\n', flags=re.IGNORECASE)).strip()
                if '}' in self['geometry']:
                    self['geometry'] = re.sub('}.*$', '', self['geometry']).strip()
                else:
                    geometry_active = True
                # print('self[geometry]',self['geometry'])
            elif geometry_active:
                assert "should not be here" != ""
                self['geometry'] += re.sub(' *[}!].*$', '', line)
                self['geometry'] = self['geometry'].rstrip(' \n') + '\n'
                geometry_active = not re.match('.*}.*', line)
            elif re.match('^geometry *=', line, re.IGNORECASE):
                if 'steps' in self and self['steps']: self.data.clear(); return self  # input too complex
                if 'geometry' in self: self.data.clear(); return self  # input too complex
                self['geometry'] = re.sub('geometry *= *', '', line, flags=re.IGNORECASE)
                self['geometry'] = re.sub(' *!.*', '', self['geometry'])
                self['geometry_external'] = True
            elif command == 'basis':
                raise ValueError('** warning should not happen basis', line)
            elif re.match('^basis *= *[^{]', line, re.IGNORECASE):
                if 'steps' in self and self['steps']: self.data.clear(); return self  # input too complex
                self['basis'] = {'default': (re.sub(',.*', '', re.sub(' *basis *= *{*(default=)*', '',
                                                                      group.replace('{', '').replace('}', ''),
                                                                      flags=re.IGNORECASE)))}
                fields = line.replace('}', '').split(',')
                self['basis']['elements'] = {}
                for field in fields[1:]:
                    ff = field.split('=')
                    self['basis']['elements'][ff[0][0].upper() + ff[0][1:].lower()] = ff[1].strip('\n ')
                # print('made basis specification',self)
            elif re.match('^basis *=', line, re.IGNORECASE):
                print('** warning should not happen')
                pass
            elif re.match('(set,)?[a-z][a-z0-9_]* *=.*$', line, flags=re.IGNORECASE):
                if debug: print('variable')
                line = re.sub(' *!.*$', '', re.sub('set *,', '', line, flags=re.IGNORECASE)).strip()
                while (
                        newline := re.sub(r'(\[[0-9!]+),', r'\1!',
                                          line)) != line: line = newline  # protect eg occ=[3,1,1]
                fields = line.split(',')
                for field in fields:
                    key = re.sub(' *=.*$', '', field)
                    value = re.sub('.*= *', '', field)
                    # print('field, key=', key, 'value=', value)
                    variables[key] = value.replace('!', ',')  # unprotect
            elif command in parameter_commands.values():
                spec_field = [k for k, v in parameter_commands.items() if v == command][0]
                fields = re.sub('^ *' + command.lower() + ' *,*', '', line.strip().lower(), flags=re.IGNORECASE).split(
                    ',')
                self[spec_field] = {
                    field.split('=')[0].strip().lower(): field.split('=')[1].strip().lower() if len(
                        field.split('=')) > 1 else '' for field in fields}
                if '' in self[spec_field]: del self[spec_field]['']

            elif command == 'core':
                self['core_correlation'] = (line + ',').split(',')[1].lower()
            elif any([re.fullmatch('{?' + df_prefix + re.escape(method), command,
                                   flags=re.IGNORECASE) for
                      df_prefix
                      in df_prefixes
                      for method in self.allowed_methods + ['optg', 'frequencies']]):
                step = {}
                method_ = command
                if command[:3] == 'df-':
                    self['density_fitting'] = True
                    method_ = command[3:]
                elif command[:4] == 'pno-' or command[:4] == 'ldf-':
                    self['density_fitting'] = True
                elif 'density_fitting' in self and self['density_fitting'] and not any(
                        [step_['command'] == command for job_type in job_type_steps for step_ in
                         job_type_steps[job_type]]):
                    self.data.clear()
                    return self
                method_options = (re.sub(';.*$', '', line.lower()).replace('}', '') + ',').split(',', 1)[1]

                method_options_ = method_options.strip(', \n').split(',')
                if method_options_ and method_options_[-1] == '': method_options_ = method_options_[:-2]
                # print('method_options_',method_options_)
                step['command'] = method_
                if method_options_:
                    step['options'] = method_options_
                # TODO parsing of extras from following directives
                # print('group before directives',group)
                directives = group.replace('}', '').split(';')[1:]
                # print('directives', directives)
                # print('intial step', step)
                for directive in directives:
                    cmd, opt = (directive + ',').split(',', 1)
                    # print('cmd',cmd,'opt',opt)
                    opts = {m1.split('=')[0].strip(): (m1.split('=')[1].strip() if len(m1.split('=')) > 1 else '') for
                            m1 in opt.rstrip(',').split(',')}
                    if '' in opts: del opts['']
                    if 'directives' not in step: step['directives'] = []
                    opts = opt.rstrip(',').split(',')
                    if opts and opts[-1] == '': opts = opts[:-2]
                    d = {'command': cmd}
                    if opts: d['options'] = opts
                    step['directives'].append(d)
                # print('step', step)
                self['steps'].append(step)
            elif any([re.match('{? *' + postscript, command, flags=re.IGNORECASE) for postscript in postscripts]):
                if 'postscripts' not in self: self['postscripts'] = []
                self['postscripts'].append(line.lower())

        # if 'method' not in self and 'precursor_methods' in self:
        #     parse_method(self, self['precursor_methods'][-1])
        #     self['precursor_methods'].pop()
        if variables:
            self['variables'] = variables
        if 'hamiltonian' not in self:
            self['hamiltonian'] = self.basis_hamiltonian
        # spin_ = self.open_shell_electrons
        # print('initial spin_',spin_)
        # if 'variables' in self and 'spin' in self['variables'] and int(self['variables']['spin'])%2 == spin_%2:
        #     spin_ = self['variables']['spin']
        # if 'variables' not in self: self['variables'] = {}
        # self['variables']['spin'] = spin_
        return self

    def input(self):
        r"""
        Create a Molpro input from a declarative specification
        :param self:
        :return:
        :rtype: str
        """
        _input = ''
        if 'orientation' in self:
            _input += 'orient,' + orientation_options[self['orientation']] + '\n'

        if 'wave_fct_symm' in self:
            _input += wave_fct_symm_commands[self['wave_fct_symm']] + '\n'

        if 'geometry' in self:
            _input += ('geometry=' + self[
                'geometry'] + '\n' if 'geometry_external' in self else 'geometry={\n' +
                                                                       self[
                                                                           'geometry']).rstrip(
                ' \n') + '\n' + ('' if 'geometry_external' in self else '}\n')

        if 'basis' in self:
            _input += 'basis=' + self['basis']['default']
            if 'elements' in self['basis']:
                for e, b in self['basis']['elements'].items():
                    _input += ',' + e + '=' + b
            _input += '\n'
        if 'variables' not in self: self['variables'] = {}
        if self['hamiltonian'][:2] == 'DK':
            self['variables']['dkho'] = self['hamiltonian'][2] if len(
                self['hamiltonian']) > 2 else '1'
        elif 'dkho' in self['variables']:
            del self['variables']['dkho']
        if 'variables' in self:
            for k, v in self['variables'].items():
                if v != '' and (k != 'charge' or v != '0'):
                    _input += k + '=' + v + '\n'
        if len(self['variables']) == 0: del self['variables']
        if 'properties' in self:
            for p in self['properties']:
                _input += properties[p] + '\n'
        for typ, command in parameter_commands.items():
            if typ in self and len(self[typ]) > 0:
                _input += command
                for k, v in self[typ].items():
                    _input += ',' + k.lower() + ('=' + str(v) if str(v) != '' else '')
                _input += '\n'
        if 'core_correlation' in self:
            _input += 'core,' + self['core_correlation'] + '\n'
        for step in (self['steps'] if 'steps' in self else []):
            _input += '{'
            if 'density_fitting' in self and self['density_fitting'] and not any(
                    [step_['command'] == step['command'] for step_ in job_type_steps[self.job_type]]) and step[
                                                                                                              'command'].lower()[
                                                                                                          :4] != 'pno-' and \
                    step['command'].lower()[:4] != 'ldf-':
                _input += 'df-'
            _input += step['command']
            # if re.match('[ru]ks', step['command'], re.IGNORECASE) and 'density_functional' in step:
            #     _input += ',' + step['density_functional']
            if 'options' in step:
                for option in step['options']:
                    _input += ',' + str(option)
            if 'directives' in step:
                for directive in step['directives']:
                    _input += ';' + directive['command']
                    if 'options' in directive:
                        for option in directive['options']:
                            _input += ',' + str(option)
            _input += '}\n'
        if 'orbitals' in self:
            for k in self['orbitals']:
                _input += orbital_types[k]['command'] + '\n'
                _input += 'put,molden,' + k + '.molden' + '\n'
        if 'postscripts' in self:
            for m in self['postscripts']:
                _input += m + '\n'
        return _input.rstrip('\n') + '\n'

    # def force_job_type(self, job_type):
    #     r"""
    #     Force the specification to be compliant with a particular job type
    #
    #     :param job_type: Force the job type to be this, and make specification['steps'] compliant.
    #     :type job_type: str
    #     """
    #     if not 'steps' in self:
    #         self['steps'] = []
    #     for step in job_type_steps[job_type]:
    #         if not any([step_['command'] == step['command'] for step_ in self['steps']]):
    #             # print('appending', step)
    #             self['steps'].append(step)
    #     for step in self['steps']:
    #         if not any([step_['command'] == step['command'] for step_ in job_type_steps]):
    #             # print('removing', step)
    #             del self['steps'][step]

    @property
    def job_type(self):
        r"""
        Deduce the job type from the stored input specification
        :return: job type, or None if the input is complex
        :rtype: str
        """
        for job_type_ in job_type_steps:
            ok = True
            last_idx = None
            for step in job_type_steps[job_type_]:
                commands = [s['command'].lower() for s in self['steps']]
                idx = commands.index(step['command'].lower()) if step['command'].lower() in commands else -1
                if idx < 0 or (last_idx is not None and last_idx != idx - 1):
                    ok = False
                last_idx = idx
            if ok: job_type = job_type_
        return job_type

    @job_type.setter
    def job_type(self, new_job_type):
        if self.job_type == new_job_type: return
        if 'steps' not in self: self['steps'] = []
        old_len = len(self['steps'])
        new_steps = [
                        step for step in self['steps']
                        if step['command'].lower() not in [s['command'].lower() for j in job_type_steps for s in
                                                           job_type_steps[j]]
                    ] + job_type_steps[new_job_type]
        for new_step in new_steps:
            for step in self['steps']:
                if step['command'].lower() == new_step['command'].lower() and 'options' in step:
                    new_step['options'] = step['options']
        self['steps'] = new_steps

    @property
    def method(self):
        r"""
        Evaluate the single method implemented by the job
        :return: If the input implements a single method, its command name. Otherwise, None
        :rtype: str
        """
        methods = []
        if 'steps' in self:
            for i in range(len(self['steps'])):
                command = self['steps'][i]['command'].lower()
                if command not in [s['command'].lower() for t in job_type_steps.values() for s in t]:
                    methods.append(command)
                    if command not in [m.lower() for m in self.hartree_fock_methods] and methods[0] in [m.lower() for m
                                                                                                        in
                                                                                                        self.hartree_fock_methods]:
                        del methods[0]
        # print('methods',methods)
        if len(methods) == 1: return methods[0]

    @method.setter
    def method(self, method):
        r"""
        Adjust the steps of specification so that they perform a specific single method
        :param method:
        :type method: str
        """
        if method is None or method == '' or (self.method is not None and method.lower() == self.method.lower()): return
        new_steps = []
        if method.lower() not in [m.lower() for m in self.hartree_fock_methods]:
            new_steps.append({'command': ('rhf' if method[0].lower() != 'u' else 'uhf')})  # TODO df
        new_steps.append({'command': method.lower()})
        if 'steps' in self:
            for step in self['steps']:
                if any([step_['command'] == step['command'] for step_ in job_type_steps[self.job_type]]):
                    new_steps.append(step)
        self['steps'] = new_steps

    @property
    def method_options(self):
        r"""Get the options for a single-method job
        """
        if 'steps' in self:
            for step in self['steps']:
                if self.method == step['command'] and 'options' in step:
                    return step['options']
        return []

    @method_options.setter
    def method_options(self, options):
        r"""
        Set the options for a single-method job
        """
        if 'steps' in self:
            for step in self['steps']:
                if self.method == step['command']:
                    step['options'] = options

    @method_options.deleter
    def method_options(self):
        if 'steps' in self:
            for step in self['steps']:
                if self.method == step['command']:
                    del step['options']

    @property
    def basis_quality(self):
        quality_letters = {2: 'D', 3: 'T', 4: 'Q', 5: '5', 6: '6', 7: '7'}
        if 'basis' in self:
            bases = [self['basis']['default']]
            if 'elements' in self['basis']: bases += self['basis']['elements'].values()
            qualities = []
            for basis in bases:
                quality = 0
                for q, l in quality_letters.items():
                    if re.match(r'.*V\(?.*' + l, basis, flags=re.IGNORECASE): quality = q
                qualities.append(quality)
            if all(quality == qualities[0] for quality in qualities):
                return qualities[0]
        return 0

    @property
    def basis_hamiltonian(self):
        result = 'AE'
        for v, k in hamiltonians.items():
            if k and 'basis' in self and 'default' in self['basis'] and k['basis_string'] in \
                    self['basis']['default']: result = v
        if 'variables' in self and 'dkho' in self['variables']:
            result = 'DK' + str(self['variables']['dkho']) if str(
                self['variables']['dkho']) != '1' else 'DK'
        return result

    @property
    def density_functional(self):
        if self.method is not None and self.method.lower() in [m.lower() for m in
                                                               self.hartree_fock_methods] and 'ks' in self.method.lower():
            if self.method_options is not None and self.method_options:
                return self.method_options[0].upper()

    @density_functional.setter
    def density_functional(self, density_functional):
        if self.method is not None and self.method.lower() in [m.lower() for m in
                                                               self.hartree_fock_methods] and 'ks' in self.method.lower():
            if self.method_options is not None and self.method_options:
                self.method_options[0] = density_functional
            else:
                self.method_options = [density_functional]

    @property
    def open_shell_electrons(self):
        r"""
        Evaluate the number of open-shell electrons in the molecule's normal state.  This will typically be 0 or 1, but for some special cases (eg atoms) might be higher.
        :return:
        :rtype: int
        """
        # TODO set up a cache if input has not changed and geometry file has not changed
        from defbas import periodic_table
        if 'geometry' not in self: return 0
        # print('enter open_shell_electrons')
        if 'geometry_external' in self and self['geometry_external']:
            # print('geometry',self['geometry'])
            # print('directory',self.directory)
            # print(pathlib.Path(self.directory if self.directory is not None else '.') / self['geometry'])
            try:
                with open(pathlib.Path(self.directory if self.directory is not None else '.') / self['geometry'],
                          'r') as f:
                    geometry = ''.join(f.readlines())
            except:
                return 0
        else:
            geometry = self['geometry']
        # print('geometry',geometry)
        line_number = 0
        start_line = 1
        total_nuclear_charge = 0
        for line in geometry.replace(';', '\n').split('\n'):
            line_number += 1
            if line.strip().isdigit() and line_number == 1: start_line = 3
            if line_number >= start_line and line:
                word = line.strip().replace(' ', ',').split(',')[0]
                word = re.sub(r'\d.*$', '', word[0].upper() + word[1:].lower())
                atomic_number = periodic_table.index(word) + 1
                total_nuclear_charge += atomic_number
        charge = int(self['variables']['charge']) if 'variables' in self and 'charge' in self['variables'] and \
                                                     self['variables']['charge'] != '' and self['variables'][
                                                         'charge'] != '-' else 0
        total_electrons = total_nuclear_charge - charge
        # print('total_nuclear_charge',total_nuclear_charge,'total_electrons',total_electrons)
        electrons = total_electrons % 2
        # implementing default spin > 1 is tricky because of handling of input files that do not contain spin specification
        # if atomic_number == total_nuclear_charge:
        #     if total_electrons in [6, 8, 14, 16, 32, 34, 50, 52, 82, 84]: electrons = 2
        #     if total_electrons in [7, 15, 33, 51, 83]: electrons = 3
        # print('Electrons: ' + str(electrons))
        return electrons

    @property
    def spin(self):
        r"""
        Evaluate 2*S
        :return: 2*S, or if unspecified, minus the electron count %2
        :rtype: int
        """
        # print('spin',self['variables'],self.open_shell_electrons)
        spin = int(self['variables']['spin']) if 'variables' in self and 'spin' in self[
            'variables'] else (self.open_shell_electrons) % 2 - 2
        # print('calculated spin',spin)
        return spin

    @spin.setter
    def spin(self, value):
        if value is None:
            if 'variables' in self and 'spin' in self['variables']:
                del self['variables']['spin']
            return
        try:
            value_ = int(value)
            if value_ % 2 != self.open_shell_electrons % 2: raise ValueError
        except ValueError:
            value_ = self.open_shell_electrons % 2
        # print('in spin setter, value=', value,value_, 'electrons', self.open_shell_electrons)
        if 'variables' not in self:
            self['variables'] = {}
        self['variables']['spin'] = str(value_)

    def polish(self):
        self.clean_coupled_cluster_property_input()

    def clean_coupled_cluster_property_input(self):
        for step in self['steps']:
            if step['command'].lower()[:4] in ['ccsd', 'bccd', 'qcisd']:
                if 'directives' in step:
                    for directive in step['directives']:
                        if directive['command'].lower() == 'expec':
                            operator = directive['options'][0].lower().replace('expec,', '')
                            property = [k for k, v in properties.items() if v == 'gexpec,' + operator][0]
                            if 'properties' in self and property not in \
                                    self['properties']:
                                step['directives'].remove(directive)
                if 'properties' in self:
                    for property in self['properties']:
                        cmd = properties[property]
                        operator = cmd.lower().replace('gexpec,', '').strip()
                        directive = {'command': 'expec', 'options': [operator]}
                        if 'directives' not in step or directive not in step['directives']:
                            if 'directives' not in step:
                                step['directives'] = []
                            step['directives'].append(directive)


def canonicalise(input):
    result = re.sub('\n}', '}',
                    re.sub(' *= *', '=',
                           re.sub('{\n', r'{',
                                  re.sub('\n+', '\n',
                                         re.sub(' *, *', ',',
                                                input.replace(';',
                                                              '\n')))))).rstrip(
        '\n ').lstrip(
        '\n ') + '\n'
    # push variable assignments below geometry=file.xyz to hack compatibility with gmolpro guided
    # print('before hack', result)
    # hack for gmolpro geomtyp:
    old_result = ''
    while (old_result != result):
        old_result = result
        result = re.sub('(\\w+=\\w+)\n(orient,mass)', '\\2\n\\1', result, flags=re.MULTILINE | re.IGNORECASE)
    old_result = ''
    while (old_result != result):
        old_result = result
        result = re.sub('(\\w+=\\w+)\n(nosym)', '\\2\n\\1', result, flags=re.MULTILINE | re.IGNORECASE)
    old_result = ''
    while (old_result != result):
        old_result = result
        result = re.sub('(\\w+=\\w+)\n(geometry=[\\w.{}]*)', '\\2\n\\1', result, flags=re.MULTILINE | re.IGNORECASE)
    old_result = ''
    while (old_result != result):
        old_result = result
        result = re.sub('(\\w+=\\w+)\n(basis={[^\n]*})', '\\2\n\\1', result,
                        flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
    # print('after 1st hack', result)
    result = re.sub('(dkho=\\d)\n(geomtyp=xyz)', '\\2\n\\1', result, flags=re.MULTILINE|re.IGNORECASE)
    # hack for gmolpro-style frequencies:
    # print('after 2nd hack', result)
    result = result.replace('{FREQ}', '{frequencies\nthermo}')
    result = re.sub('basis={\n', 'basis={', result, flags=re.IGNORECASE | re.DOTALL)
    # print('after 3rd hack', result)
    new_result = ''
    in_group = False
    for line in re.sub('set[, ]', '', result.strip(), flags=re.IGNORECASE).split('\n'):

        if not in_group:
            in_group = '{' in line
        # transform out alternate formats of basis
        line = re.sub('basis *, *', 'basis=', line.rstrip(' ,'), flags=re.IGNORECASE)
        line = re.sub('basis= *{(.*)} *(!.*)?$', r'basis=\1 \2', line, flags=re.IGNORECASE)
        line = re.sub('basis= *default *= *', r'basis=', line, flags=re.IGNORECASE).lower()
        line = re.sub(' *!.*$', '', line)
        for cmd in ['hf', 'ks']:
            for bra in ['', '{']:
                line = re.sub('^ *' + bra + ' *' + cmd, bra + 'r' + cmd, line,
                              flags=re.IGNORECASE)  # TODO unify with following

        # transform out alternate spin markers
        # for m in initial_orbital_methods:
        #     line = re.sub('r' + m, m, line, flags=re.IGNORECASE)
        # transform in alternate spin markers
        for m in initial_orbital_methods:
            line = re.sub('^{' + m, '{r' + m.lower(), line, flags=re.IGNORECASE)

        if line.lower().strip() in job_type_aliases.keys(): line = job_type_aliases[line.lower().strip()]
        if line.lower().strip() in wave_fct_symm_aliases.keys():
            line = wave_fct_symm_aliases[line.lower().strip()]
        line = line.replace('!', '&&&&&')  # protect trailing comments
        while (newline := re.sub(r'(\[[0-9!]+),', r'\1!', line)) != line: line = newline  # protect eg occ=[3,1,1]
        if re.match(r'[a-z][a-z0-9_]* *= *\[?[!a-z0-9_. ]*\]? *,', line, flags=re.IGNORECASE):
            line = line.replace(',', '\n')
        line = re.sub(' *}', '}', line)
        line = re.sub('{ *', '{', line)
        line = line.replace('!', ',').strip() + '\n'  # unprotect
        line = line.replace('&&&&&', '!').strip() + '\n'  # unprotect
        # print('line before bracketing',line, in_group)
        if line.strip() and line.strip()[0] != '{' and not re.match(r'^ *\w+ *=', line) and not in_group and not any(
                [v in line for v in parameter_commands.values()]):
            comment_split = line.split('!')
            line = '{' + comment_split[0].strip() + '}'  # + (comment_split[1] if len(comment_split) > 1 else '')
        # print('line after bracketing',line)
        in_group = in_group and not '}' in line
        if line.strip('\n') != '':
            new_result += line.strip('\n ') + '\n'
    return new_result.strip('\n ') + '\n'


def equivalent(input1, input2, debug=False):
    if isinstance(input1, InputSpecification): return equivalent(input1.input(), input2, debug)
    if isinstance(input2, InputSpecification): return equivalent(input1, input2.input(), debug)
    if debug:
        print('equivalent: input1=', input1)
        print('equivalent: input2=', input2)
        print('equivalent: canonicalise(input1)=', canonicalise(input1))
        print('equivalent: canonicalise(input2)=', canonicalise(input2))
        print('will return this', canonicalise(input1).lower() == canonicalise(input2).lower())
    return canonicalise(input1).lower() == canonicalise(input2).lower()
