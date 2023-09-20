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

    precursor_methods = ['HF', 'KS', 'LOCALI', 'CASSCF']
    methods = ['HF', 'KS', 'MP2', 'CCSD', 'CCSD(T)', 'MRCI', 'RS2', 'RS2C']
    spin_prefixes = ['', 'R', 'U']
    local_prefixes = ['', 'L']
    df_prefixes = ['', 'DF-', 'PNO-']

    specification = {}
    variables = {}
    geometry_active = False
    basis_active = False
    for line in input.replace(';', '\n').split('\n'):
        line = line.strip()
        command = re.sub('[, !].*$', '', line, flags=re.IGNORECASE)
        if re.match('^geometry *= *{', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            if 'geometry' in specification: return {}  # input too complex
            specification['geometry'] = re.sub('^geometry *= *{ *\n*', '', line+'\n', flags=re.IGNORECASE)
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
            specification['basis'] = re.sub('^basis *= *{', '', line, flags=re.IGNORECASE)
            if '}' in specification['basis']:
                specification['basis'] = re.sub('}.*$', '', specification['basis'])
            else:
                basis_active = True
        elif basis_active:
            specification['basis'] += ('\n' + re.sub(' *[}!].*$', '', line)).rstrip(' \n') + '\n'
            basis_active = not re.match('.*}.*', line)
        elif re.match('^basis *=', line, re.IGNORECASE):
            if 'precursor_methods' in specification: return {}  # input too complex
            if 'method' in specification: return {}  # input too complex
            basis = re.sub('basis *= *', '', line, flags=re.IGNORECASE)
            basis = re.sub(' *!.*', '', basis)
            specification['basis'] = 'default=' + basis
        elif any(
                [re.match('{?' + df_prefix + spin_prefix + precursor_method, command, flags=re.IGNORECASE) for df_prefix
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
        elif re.match('(set,)?[a-z][a-z0-9_]* *=.*$', line, flags=re.IGNORECASE):
            line = re.sub(' *!.*$', '', re.sub('set *,', '', line, flags=re.IGNORECASE)).strip()
            while (newline := re.sub('(\[[[0-9!]*),',r'\1!',line)) != line: line = newline # protect eg occ=[3,1,1]
            fields = line.split(',')
            for field in fields:
                key=re.sub(' *=.*$','',field)
                value=re.sub('.*= *','',field)
                variables[key]=value.replace('!',',') # unprotect
        else:
            pass
    if 'method' not in specification and 'precursor_methods' in specification:
        specification['method'] = specification['precursor_methods'][-1]
        specification['precursor_methods'].pop()
    if variables:
        specification['variables']=variables
    return specification


def create_input(specification: dict):
    r"""
    Create a Molpro input from a declarative specification
    :param specification:
    :return:
    :rtype: str
    """
    input=''
    if 'variables' in specification:
        for k,v in specification['variables'].items():
            input += k+'='+v+'\n'
    if 'geometry' in specification:
        input += ('geometry=' + specification['geometry'] + '\n' if 'geometry_external' in specification else 'geometry={\n' +
                                                                                                         specification[
                                                                                                             'geometry']).rstrip(
        ' \n') + '\n' + '}\n'
    if 'basis' in specification:
        input += 'basis={' + specification['basis'] + '}\n'
    if 'precursor_methods' in specification:
        for m in specification['precursor_methods']:
            input += m + '\n'
    if 'method' in specification:
        input += specification['method'] + '\n'
    return input.rstrip('\n')+'\n'


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
