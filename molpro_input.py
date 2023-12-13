import os
import re

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

job_type_commands = {
    'Single Point Energy': '',
    'Geometry Optimisation': 'optg',
    'Opt+Frequency': 'optg; frequencies',
    'Hessian': 'frequencies',
}
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


def parse(input: str, allowed_methods=[], debug=False):
    r"""
    Take a molpro input, and logically parse it, on the assumption that it's a single-task input.

    :param input: Either text that is the input, or a file name containing it.
    :return:
    :rtype dict:
    """
    if os.path.exists(input):
        return parse(open(input, 'r').read())

    precursor_methods = ['HF', 'KS', 'LOCALI', 'CASSCF', 'OCC', 'CORE', 'CLOSED', 'FROZEN', 'WF', 'LOCAL', 'DFIT',
                         'DIRECT', 'EXPLICIT', 'THRESH', 'GTHRESH', 'PRINT', 'GRID']
    spin_prefixes = ['', 'R', 'U']
    local_prefixes = ['', 'L']
    df_prefixes = ['', 'DF-', 'PNO-']
    postscripts = ['PUT', 'TABLE', 'NOORBITALS', 'NOBASIS']  # FIXME not very satisfactory

    specification = {}
    variables = {}
    geometry_active = False

    specification['job_type'] = 'Single Point Energy'
    for line in canonicalise(input).split('\n'):
        line = line.strip()
        command = re.sub('[, !].*$', '', line, flags=re.IGNORECASE)
        if re.match('^orient *, *', line, re.IGNORECASE):
            line = re.sub('^orient *, *', '', line, flags=re.IGNORECASE)
            for orientation_option in orientation_options.keys():
                if (line.lower() == orientation_options[orientation_option].lower()):
                    specification['orientation'] = orientation_option
                    break
        elif ((command.lower() == 'nosym') or (re.match('^symmetry *, *', line, re.IGNORECASE))):
            line = re.sub('^symmetry *, *', '', line, flags=re.IGNORECASE)
            line = "symmetry," + line
            for symmetry_command in wave_fct_symm_commands.keys():
                if (line.lower() == wave_fct_symm_commands[symmetry_command]):
                    specification['wave_fct_symm'] = symmetry_command
                    break
        elif re.match('^geometry *= *{', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            if 'geometry' in specification: return {}  # input too complex
            specification['geometry'] = re.sub('^geometry *= *{ *\n*', '', line + '\n', flags=re.IGNORECASE)
            if '}' in specification['geometry']:
                specification['geometry'] = re.sub('}.*$', '', specification['geometry'])
            else:
                geometry_active = True
        elif geometry_active:
            specification['geometry'] += re.sub(' *[}!].*$', '', line)
            specification['geometry'] = specification['geometry'].rstrip(' \n') + '\n'
            geometry_active = not re.match('.*}.*', line)
        elif re.match('^geometry *=', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            if 'geometry' in specification: return {}  # input too complex
            specification['geometry'] = re.sub('geometry *= *', '', line, flags=re.IGNORECASE)
            specification['geometry'] = re.sub(' *!.*', '', specification['geometry'])
            specification['geometry_external'] = True
        elif command == 'basis':
            raise ValueError('** warning should not happen basis', line)
            specification['basis'] = 'default=' + re.sub('^basis *, *', '', line, flags=re.IGNORECASE).rstrip('\n ')
        elif re.match('^basis *= *', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            specification['basis'] = {'default': (re.sub(' *basis *= *', '', command))}
            fields = line.split(',')
            specification['basis']['elements'] = {}
            for field in fields[1:]:
                ff = field.split('=')
                specification['basis']['elements'][ff[0][0].upper() + ff[0][1:].lower()] = ff[1].strip('\n ')
            specification['basis']['quality'] = basis_quality(specification)
            # print('made basis specification',specification)
        elif re.match('^basis *=', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            basis = re.sub('basis *= *', '', line, flags=re.IGNORECASE)
            basis = re.sub(' *!.*', '', basis)
            specification['basis'] = 'default=' + basis
        elif re.match('(set,)?[a-z][a-z0-9_]* *=.*$', line, flags=re.IGNORECASE):
            # print('variable found, line=', line)
            if debug: print('variable')
            line = re.sub(' *!.*$', '', re.sub('set *,', '', line, flags=re.IGNORECASE)).strip()
            while (newline := re.sub(r'(\[[0-9!]+),', r'\1!', line)) != line: line = newline  # protect eg occ=[3,1,1]
            fields = line.split(',')
            for field in fields:
                key = re.sub(' *=.*$', '', field)
                value = re.sub('.*= *', '', field)
                # print('field, key=', key, 'value=', value)
                variables[key] = value.replace('!', ',')  # unprotect
        elif any(
                [re.match('{? *' + df_prefix + spin_prefix + precursor_method + '[;}]', command + ';',
                          flags=re.IGNORECASE) for
                 df_prefix
                 in
                 df_prefixes
                 for spin_prefix in spin_prefixes for precursor_method in precursor_methods]):
            if 'method' in specification: return {}  # input too complex
            if 'precursor_methods' not in specification: specification['precursor_methods'] = []
            specification['precursor_methods'].append(line.lower())
        elif any([re.fullmatch('{?' + df_prefix + local_prefix + spin_prefix + re.escape(method), command,
                               flags=re.IGNORECASE) for
                  df_prefix
                  in df_prefixes
                  for local_prefix in local_prefixes for spin_prefix in spin_prefixes for method in allowed_methods]):
            specification['method'] = line.lower()
        elif command != '' and (any(
                [command.lower() == re.sub('.*; ', '', job_type_commands[job_type].lower()) for job_type in
                 job_type_commands.keys() if job_type != '']) or command.lower() in job_type_aliases.keys()):
            old_job_type_command = job_type_commands[specification['job_type']]  # to support optg; freq
            job_type_command = command.lower()
            if job_type_command in job_type_aliases.keys():
                job_type_command = job_type_aliases[job_type_command]
            for job_type in job_type_commands.keys():
                if job_type_command == re.sub('.*; ', '', job_type_commands[job_type].lower()):
                    specification['job_type'] = job_type
            if old_job_type_command == 'optg' and job_type_command == 'frequencies':
                job_type_command = 'optg; frequencies'
            specification['job_type'] = \
                [job_type for job_type in job_type_commands.keys() if job_type_commands[job_type] == job_type_command][
                    0]
        elif any([re.match('{? *' + postscript, command, flags=re.IGNORECASE) for postscript in postscripts]):
            if 'postscripts' not in specification: specification['postscripts'] = []
            specification['postscripts'].append(line.lower())

    if 'method' not in specification and 'precursor_methods' in specification:
        specification['method'] = specification['precursor_methods'][-1]
        specification['precursor_methods'].pop()
    if variables:
        specification['variables'] = variables
    if 'hamiltonian' not in specification:
        specification['hamiltonian'] = basis_hamiltonian(specification)
    return specification


def create_input(specification: dict):
    r"""
    Create a Molpro input from a declarative specification
    :param specification:
    :return:
    :rtype: str
    """
    _input = ''
    if 'orientation' in specification:
        _input += 'orient,' + orientation_options[specification['orientation']] + '\n'

    if 'wave_fct_symm' in specification:
        _input += wave_fct_symm_commands[specification['wave_fct_symm']] + '\n'

    if 'geometry' in specification:
        _input += ('geometry=' + specification[
            'geometry'] + '\n' if 'geometry_external' in specification else 'geometry={\n' +
                                                                            specification[
                                                                                'geometry']).rstrip(
            ' \n') + '\n' + ('' if 'geometry_external' in specification else '}\n')

    if 'basis' in specification:
        _input += 'basis=' + specification['basis']['default']
        if 'elements' in specification['basis']:
            for e, b in specification['basis']['elements'].items():
                _input += ',' + e + '=' + b
        _input += '\n'
    if 'variables' in specification:
        for k, v in specification['variables'].items():
            if v != '':
                _input += k + '=' + v + '\n'
    if 'precursor_methods' in specification:
        for m in specification['precursor_methods']:
            _input += m + '\n'
    if 'method' in specification:
        _input += specification['method'] + '\n'
    if 'job_type' in specification:
        _input += job_type_commands[specification['job_type']] + '\n'
    if 'postscripts' in specification:
        for m in specification['postscripts']:
            _input += m + '\n'
    return _input.rstrip('\n') + '\n'


def basis_quality(specification):
    quality_letters = {2: 'D', 3: 'T', 4: 'Q', 5: '5', 6: '6', 7: '7'}
    if 'basis' in specification:
        bases = [specification['basis']['default']]
        if 'elements' in specification['basis']: bases += specification['basis']['elements'].values()
        qualities = []
        for basis in bases:
            quality = 0
            for q, l in quality_letters.items():
                if re.match(r'.*V\(?.*' + l, basis, flags=re.IGNORECASE): quality = q
            qualities.append(quality)
        if all(quality == qualities[0] for quality in qualities):
            return qualities[0]
    return 0


def basis_hamiltonian(specification):
    result = 'AE'
    for v, k in hamiltonians.items():
        if k and 'basis' in specification and 'default' in specification['basis'] and k['basis_string'] in \
                specification['basis']['default']: result = v
    # print('basis_hamiltonian: ', result)
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
    for line in re.sub('set[, ]', '', result.strip(), flags=re.IGNORECASE).split('\n'):

        # transform out alternate formats of basis
        line = re.sub('basis *, *', 'basis=', line, flags=re.IGNORECASE)
        line = re.sub('basis= *{(.*)} *$', r'basis=\1', line, flags=re.IGNORECASE)
        line = re.sub('basis= *default *= *', r'basis=', line, flags=re.IGNORECASE)

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
        if line.strip('\n') != '':
            new_result += line.strip('\n ') + '\n'
    return new_result.strip('\n ') + '\n'


def equivalent(input1, input2, debug=False):
    if type(input1) == dict: return equivalent(create_input(input1), input2, debug)
    if type(input2) == dict: return equivalent(input1, create_input(input2), debug)
    if debug:
        print('equivalent: input1=', input1)
        print('equivalent: input2=', input2)
        print('equivalent: canonicalise(input1)=', canonicalise(input1))
        print('equivalent: canonicalise(input2)=', canonicalise(input2))
        print('will return this', canonicalise(input1).lower() == canonicalise(input2).lower())
    return canonicalise(input1).lower() == canonicalise(input2).lower()
