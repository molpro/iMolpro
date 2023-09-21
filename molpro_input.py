import os
import re


def parse(input: str):
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
    methods = ['HF', 'KS', 'MP2', 'CCSD', 'CCSD(T)', 'MRCI', 'RS2', 'RS2C']
    spin_prefixes = ['', 'R', 'U']
    local_prefixes = ['', 'L']
    df_prefixes = ['', 'DF-', 'PNO-']
    postscripts = ['PUT', 'TABLE']

    specification = {}
    variables = {}
    geometry_active = False
    basis_active = False
    for line in canonicalise(input).split('\n'):
        line = line.strip()
        command = re.sub('[, !].*$', '', line, flags=re.IGNORECASE)
        if re.match('^geometry *= *{', line, re.IGNORECASE):
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
        elif re.match('^basis *= *{', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            specification['basis'] = re.sub('^basis *= *{', '', line, flags=re.IGNORECASE).rstrip('\n ')
            if '}' in specification['basis']:
                specification['basis'] = re.sub('}.*$', '', specification['basis']).rstrip('\n ')
            else:
                basis_active = True
        elif basis_active:
            specification['basis'] += ('\n' + re.sub(' *[}!].*$', '', line)).strip(' \n')
            basis_active = not re.match('.*}.*', line)
        elif re.match('^basis *=', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            basis = re.sub('basis *= *', '', line, flags=re.IGNORECASE)
            basis = re.sub(' *!.*', '', basis)
            specification['basis'] = 'default=' + basis
        elif re.match('(set,)?[a-z][a-z0-9_]* *=.*$', line, flags=re.IGNORECASE):
            line = re.sub(' *!.*$', '', re.sub('set *,', '', line, flags=re.IGNORECASE)).strip()
            while (newline := re.sub('(\[[[0-9!]*),', r'\1!', line)) != line: line = newline  # protect eg occ=[3,1,1]
            fields = line.split(',')
            for field in fields:
                key = re.sub(' *=.*$', '', field)
                value = re.sub('.*= *', '', field)
                variables[key] = value.replace('!', ',')  # unprotect
        elif any(
                [re.match('{? *' + df_prefix + spin_prefix + precursor_method + '}?', command, flags=re.IGNORECASE) for
                 df_prefix
                 in
                 df_prefixes
                 for spin_prefix in spin_prefixes for precursor_method in precursor_methods]):
            if 'method' in specification: return {}  # input too complex
            if 'precursor_methods' not in specification: specification['precursor_methods'] = []
            specification['precursor_methods'].append(line.lower())
        elif any([re.match('{?' + df_prefix + local_prefix + spin_prefix + method, command, flags=re.IGNORECASE) for
                  df_prefix
                  in df_prefixes
                  for local_prefix in local_prefixes for spin_prefix in spin_prefixes for method in methods]):
            specification['method'] = line.lower()
        elif any([re.match(postscript, command, flags=re.IGNORECASE) for postscript in postscripts]):
            if 'postscripts' not in specification: specification['postscripts'] = []
            specification['postscripts'].append(line.lower())
        else:
            pass
    if 'method' not in specification and 'precursor_methods' in specification:
        specification['method'] = specification['precursor_methods'][-1]
        specification['precursor_methods'].pop()
    if variables:
        specification['variables'] = variables
    return specification


def create_input(specification: dict):
    r"""
    Create a Molpro input from a declarative specification
    :param specification:
    :return:
    :rtype: str
    """
    input = ''
    if 'variables' in specification:
        for k, v in specification['variables'].items():
            input += k + '=' + v + '\n'
    if 'geometry' in specification:
        input += ('geometry=' + specification[
            'geometry'] + '\n' if 'geometry_external' in specification else 'geometry={\n' +
                                                                            specification[
                                                                                'geometry']).rstrip(
            ' \n') + '\n' + ('' if 'geometry_external' in specification else '}\n')
    if 'basis' in specification:
        input += 'basis={' + specification['basis'] + '}\n'
    if 'precursor_methods' in specification:
        for m in specification['precursor_methods']:
            input += m + '\n'
    if 'method' in specification:
        input += specification['method'] + '\n'
    if 'postscripts' in specification:
        for m in specification['postscripts']:
            input += m + '\n'
    return input.rstrip('\n') + '\n'


def basis_quality(specification):
    quality_letters = {2: 'D', 3: 'T', 4: 'Q', 5: '5', 6: '6', 7: '7'}
    if 'basis' in specification:
        bases = specification['basis'].split(',')
        qualities = []
        for basis in bases:
            quality = 0
            for q, l in quality_letters.items():
                if re.match(r'.*V\(?.*' + l, basis, flags=re.IGNORECASE): quality = q
            qualities.append(quality)
        if all(quality == qualities[0] for quality in qualities):
            return qualities[0]
    return 0


def canonicalise(input):
    # return re.sub('([^\n])}',r'\1\n}',re.sub('{([^\n])',r'{\n\1',re.sub('\n+', '\n', input.replace(';','\n')))).rstrip('\n ').lstrip('\n ')+'\n'
    return re.sub('\n}', '}', re.sub('{\n', r'{', re.sub('\n+', '\n', input.replace(';', '\n')))).rstrip('\n ').lstrip(
        '\n ') + '\n'


def equivalent(input1, input2, debug=False):
    if type(input1) == dict: return equivalent(create_input(input1), input2, debug)
    if type(input2) == dict: return equivalent(input1, create_input(input2), debug)
    if debug:
        print('equivalent: input1=', input1)
        print('equivalent: input2=', input2)
        print('equivalent: canonicalise(input1)=', canonicalise(input1))
        print('equivalent: canonicalise(input2)=', canonicalise(input2))
    return canonicalise(input1) == canonicalise(input2)
