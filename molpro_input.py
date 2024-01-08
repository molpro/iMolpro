import os
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

job_type_commands = {
    'Single point energy': '',
    'Geometry optimisation': 'optg,savexyz=optimised.xyz',
    'Optimise + vib frequencies': 'optg,savexyz=optimised.xyz; frequencies',
    'Hessian': 'frequencies',
}
job_type_steps = {
    'Single point energy': [],
    'Geometry optimisation': [{'command': 'optg', 'options': {'savexyz': 'optimised.xyz'}}],
    'Hessian': [{'command': 'frequencies', 'directives': {'command': 'thermo'}}],
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
    'No orientation': 'noorient'
}

properties = {
    'Quadrupole moment': 'gexpec,qm',
    'Second moment': 'gexpec,sm',
    'Kinetic energy': 'gexpec,ekin',
    'Cowan-Griffin': 'gexpec,rel',
    'Mass-velocity': 'gexpec,massv',
    'Darwin': 'gexpec,darw',
}

initial_orbital_methods = ['HF', 'KS']

supported_methods=[]


class InputSpecification(UserDict):
    hartree_fock_methods = ['RHF', 'RKS', 'UHF', 'RHF', 'LDF-RHF', 'LDF-UHF']

    def __init__(self, input=None, allowed_methods=[], debug=False, specification=None):
        super(InputSpecification, self).__init__()
        self.allowed_methods = list(set(allowed_methods).union(set(supported_methods)))
        # print('self.allowed_methods',self.allowed_methods)
        self.debug = debug
        if specification is not None:
            for k in specification:
                self[k] = specification[k]
        if input is not None:
            self.parse(input)

    def parse(self, input: str, debug=False):
        r"""
        Take a molpro input, and logically parse it

        :param input: Either text that is the input, or a file name containing it.
        :return:
        :rtype: InputSpecification
        """
        if os.path.exists(input):
            return self.parse(open(input, 'r').read())

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
        canonicalised_input_ = input

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
                                                                                                j + 1:];
        canonicalised_input_ = canonicalised_input_.replace(';','\n').replace(line_end_protected_,';')
        for line in canonicalised_input_.split('\n'):
            line = re.sub('basis *,','basis=',line,flags=re.IGNORECASE)
            group = line.strip()
            line = group.split(line_end_protected_)[0].replace('{', '').strip()
            command = re.sub('[, !].*$', '', line, flags=re.IGNORECASE).replace('}', '').lower()
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
            elif any(
                    [re.match('put,molden,' + k + '.molden', line, flags=re.IGNORECASE) for k in orbital_types.keys()]):
                if 'orbitals' not in self: self['orbitals'] = []
                self['orbitals'].append(re.sub('put,molden, *([^.]*).*', r'\1', line))
            elif re.match('^geometry *= *{', group, re.IGNORECASE):
                # print('geometry matched')
                if 'steps' in self and self['steps']: self.data.clear(); return  # input too complex
                if 'geometry' in self: self.data.clear(); return  # input too complex
                self['geometry'] = re.sub(';','\n',re.sub('^geometry *= *{ *\n*', '', group + '\n', flags=re.IGNORECASE)).strip()
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
                if 'steps' in self and self['steps']: self.data.clear(); return  # input too complex
                if 'geometry' in self: self.data.clear(); return  # input too complex
                self['geometry'] = re.sub('geometry *= *', '', line, flags=re.IGNORECASE)
                self['geometry'] = re.sub(' *!.*', '', self['geometry'])
                self['geometry_external'] = True
            elif command == 'basis':
                raise ValueError('** warning should not happen basis', line)
                self['basis'] = 'default=' + re.sub('^basis *, *', '', line, flags=re.IGNORECASE).rstrip('\n ')
            elif re.match('^basis *= *', line, re.IGNORECASE):
                if 'steps' in self and self['steps']: self.data.clear(); return  # input too complex
                self['basis'] = {'default': (re.sub(',.*','',re.sub(' *basis *= *{*(default=)*', '', group.replace('{','').replace('}',''),flags=re.IGNORECASE)))}
                fields = line.replace('}','').split(',')
                self['basis']['elements'] = {}
                for field in fields[1:]:
                    ff = field.split('=')
                    self['basis']['elements'][ff[0][0].upper() + ff[0][1:].lower()] = ff[1].strip('\n ')
                # print('made basis specification',self)
            elif re.match('^basis *=', line, re.IGNORECASE):
                if 'steps' in self and self['steps']: self.data.clear(); return  # input too complex
                basis = re.sub('basis *= *', '', line, flags=re.IGNORECASE)
                basis = re.sub(' *!.*', '', basis)
                self['basis'] = 'default=' + basis
            elif re.match('(set,)?[a-z][a-z0-9_]* *=.*$', line, flags=re.IGNORECASE):
                if debug: print('variable')
                line = re.sub(' *!.*$', '', re.sub('set *,', '', line, flags=re.IGNORECASE)).strip()
                while (
                newline := re.sub(r'(\[[0-9!]+),', r'\1!', line)) != line: line = newline  # protect eg occ=[3,1,1]
                fields = line.split(',')
                for field in fields:
                    key = re.sub(' *=.*$', '', field)
                    value = re.sub('.*= *', '', field)
                    # print('field, key=', key, 'value=', value)
                    variables[key] = value.replace('!', ',')  # unprotect
            elif command in parameter_commands.values():
                spec_field = [k for k, v in parameter_commands.items() if v == command][0]
                fields = re.sub('^ *gthresh *,*', '', line.strip().lower(), flags=re.IGNORECASE).split(',')
                self[spec_field] = {
                    field.split('=')[0].strip().lower(): field.split('=')[1].strip().lower() if len(
                        field.split('=')) > 1 else '' for field in fields}
                if '' in self[spec_field]: del self[spec_field]['']
            # elif False and any(
            #         [re.match('{? *' + df_prefix + precursor_method + '[;}]', command + ';',
            #                   flags=re.IGNORECASE) for
            #          df_prefix
            #          in
            #          df_prefixes
            #          for precursor_method in precursor_methods]):
            #     if 'method' in self: self.data.clear(); return  # input too complex
            #     if 'precursor_methods' not in self: self['precursor_methods'] = []
            #     self['precursor_methods'].append(line.lower())
            elif any([re.fullmatch('{?' + df_prefix + re.escape(method), command,
                                   flags=re.IGNORECASE) for
                      df_prefix
                      in df_prefixes
                      for method in self.allowed_methods + ['optg', 'frequencies']]):
                step = {}
                method_ = command
                method_options = (line.lower().replace('}','') + ',').split(',', 1)[1]
                if re.match('[ru]ks', method_):
                    step['density_functional'], method_options = (method_options + ',').split(',', 1)
                method_options_ = {
                    m1.split('=')[0].strip(): (m1.split('=')[1].strip() if len(m1.split('=')) > 1 else '') for m1 in
                    method_options.rstrip(',').split(',')}
                if '' in method_options_:
                    del method_options_['']
                step['command'] = method_
                if method_options_:
                    step['options'] = method_options_
                # TODO parsing of extras from following directives
                directives = group.replace('}', '').split(line_end_protected_)[1:]
                # print('directives', directives)
                for directive in directives:
                    cmd, opt = (directive + ',').split(',', 1)
                    opts = {m1.split('=')[0].strip(): (m1.split('=')[1].strip() if len(m1.split('=')) > 1 else '') for
                            m1 in opt.rstrip(',').split(',')}
                    if '' in opts: del opts['']
                    if 'directives' not in step: step['directives'] = []
                    step['directives'].append({'command': cmd, 'options': opts})
                # print('step', step)
                self['steps'].append(step)
            elif command != '' and (any(
                    [line.lower() == job_type_commands[job_type].lower().split(';\n')[0] for job_type in
                     job_type_commands.keys() if job_type != '']) or command.lower() in job_type_aliases.keys()):
                assert 'job_type parsing should not happen here' != ''
                old_job_type_command = job_type_commands[self['job_type']]  # to support optg; freq
                job_type_command = line.lower()
                if job_type_command in job_type_aliases.keys():
                    job_type_command = job_type_aliases[job_type_command]
                for job_type in job_type_commands.keys():
                    if job_type_command == job_type_commands[job_type].lower().split(';\n')[0]:
                        self['job_type'] = job_type
                if old_job_type_command.split(',')[0] == job_type_commands['Geometry optimisation'].split(',')[
                    0] and job_type_command == 'frequencies':
                    job_type_command = job_type_commands['Optimise + vib frequencies']
                self['job_type'] = \
                    [job_type for job_type in job_type_commands.keys() if
                     job_type_commands[job_type] == job_type_command][
                        0]
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
        return self

    def create_input(self):
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
                if v != '':
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
        for step in (self['steps'] if 'steps' in self else []):
            _input += '{' + step['command']
            if re.match('[ru]ks', step['command'], re.IGNORECASE) and 'density_functional' in step:
                _input += ',' + step['density_functional']
            if 'options' in step:
                for k, v in step['options'].items():
                    _input += ',' + k + ('=' + v if str(v) != '' else '')
            if 'directives' in step['command']:
                for directive in step['command']['directives']:
                    _input += ',' + directive['command']
                    if 'options' in directive:
                        for k, v in directive['options'].items():
                            _input += ',' + k + ('=' + v if str(v) != '' else '')
            _input += '}\n'
        if 'orbitals' in self:
            for k in self['orbitals']:
                _input += orbital_types[k]['command'] + '\n'
                _input += 'put,molden,' + k + '.molden' + '\n'
        if 'postscripts' in self:
            for m in self['postscripts']:
                _input += m + '\n'
        return _input.rstrip('\n') + '\n'

    def force_job_type(self, job_type):
        r"""
        Force the specification to be compliant with a particular job type

        :param job_type: Force the job type to be this, and make specification['steps'] compliant.
        :type job_type: str
        """
        if not 'steps' in self:
            self['steps'] = []
        for step in job_type_steps[job_type]:
            if not any([step_['command'] == step['command'] for step_ in self['steps']]):
                # print('appending', step)
                self['steps'].append(step)
        for step in self['steps']:
            if not any([step_['command'] == step['command'] for step_ in job_type_steps]):
                # print('removing', step)
                del self['steps'][step]

    @property
    def job_type(self):
        r"""
        Deduce the job type from the stored input specification
        :return: job type, or None if the input is complex
        :rtype: str
        """
        for job_type_ in job_type_steps:
            try:
                for step in job_type_steps[job_type_]:
                    if not any([step_['command'] == step['command'] for step_ in self['steps']]):
                        raise ValueError('')
                for step in self['steps']:
                    if not any([step_['command'] == step['command'] for step_ in job_type_steps[job_type_]]):
                        raise ValueError('')
                return job_type_
            except:
                pass

    def force_method(self, method, options=None):
        r"""
        Adjust the steps of specification so that they perform a specific single method
        :param method:
        :type method: str
        :param options:
        :type options: dict
        """
        old_keys = list(self['steps'].keys())
        valid = True
        if method in self.hartree_fock_methods:
            start = 0
        else:
            start = 1
            valid = self['steps'][old_keys[0]] in self.hartree_fock_methods
        valid = valid and self['steps'][old_keys[start]] == method
        for key in old_keys[start+1:]:
            valid = valid and self['steps'][key]['command'] in [s['command'] for s in c for c in job_type_commands.values()]
        if valid: return
        new_steps=[]
        if method not in self.hartree_fock_methods:
            new_steps.append({'command': 'rhf'}) # TODO implement df
        new_steps.append({'command': method}) # TODO implement df
        for key in old_keys[start+1:]:
            if self['steps'][key]['command'] in [s['command'] for s in c for c in job_type_commands.values()]:
                new_steps.append(self['steps'][key])
        self['steps'] = new_steps



    @property
    def method(self):
        r"""
        If the specification implements a single method, return its command
        :return:
        :rtype:
        """
        main_method=None
        for step in self['steps']:
            if step['command'] not in [step_['command'] for step_ in job_type_steps[job_type] for job_type in job_type_steps]:
                main_method = step['command']
        for step in self['steps']:
            if step['command'] in self.hartree_fock_methods: continue
            if step['command'] == main_method:
                return main_method
            else:
                return None


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
    new_result = ''
    in_geometry = False
    for line in re.sub('set[, ]', '', result.strip(), flags=re.IGNORECASE).split('\n'):

        # if not in_geometry:
            # in_geometry = re.match(' *geometry *= *{', line, re.IGNORECASE) is not None
        #     for sep in ['=', ',']:
        #         if re.match('^{?\w+' + sep + '.*', line):
        #             line = line.split(sep, 1)[0].lower() + sep + line.split(sep, 1)[1]
        #             break
        # else:
            # in_geometry = in_geometry and not '}' in line
        # transform out alternate formats of basis
        line = re.sub('basis *, *', 'basis=', line.rstrip(' ,'), flags=re.IGNORECASE)
        line = re.sub('basis= *{(.*)} *(!.*)?$', r'basis=\1 \2', line, flags=re.IGNORECASE)
        line = re.sub('basis= *default *= *', r'basis=', line, flags=re.IGNORECASE).lower()
        line = re.sub(' *!.*$','', line)
        for cmd in ['hf','ks']:
            for bra in ['','{']:
                line=re.sub('^ *'+bra+' *'+cmd,bra+'r'+cmd, line, flags=re.IGNORECASE)

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
        # print('line before bracketing',line, in_geometry)
        if line.strip()[0]!='{' and not re.match('^ *\w+ *=',line) and not in_geometry:
            comment_split= line.split('!')
            line = '{'+comment_split[0].strip()+'}' #+ (comment_split[1] if len(comment_split) > 1 else '')
        # print('line after bracketing',line)
        if not in_geometry:
            in_geometry = re.match(' *geometry *= *{', line, re.IGNORECASE) is not None
        in_geometry = in_geometry and not '}' in line
        if line.strip('\n') != '':
            new_result += line.strip('\n ') + '\n'
    return new_result.strip('\n ') + '\n'


def equivalent(input1, input2, debug=False):
    if isinstance(input1, InputSpecification): return equivalent(input1.create_input(), input2, debug)
    if isinstance(input2, InputSpecification): return equivalent(input1, input2.create_input(), debug)
    if debug:
        print('equivalent: input1=', input1)
        print('equivalent: input2=', input2)
        print('equivalent: canonicalise(input1)=', canonicalise(input1))
        print('equivalent: canonicalise(input2)=', canonicalise(input2))
        print('will return this', canonicalise(input1).lower() == canonicalise(input2).lower())
    return canonicalise(input1).lower() == canonicalise(input2).lower()
