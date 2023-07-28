def atomic_number(el):
    elements = ['X', 'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
                'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar',
                'K', 'Ca',
                'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
                'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
                'Rb', 'Sr',
                'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
                'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
                'Cs', 'Ba',
                'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
                'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
                'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn',
                'Fr', 'Ra',
                'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No',
                'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds', 'Rg', 'Cn',
                'Nh', 'Fl', 'Mc', 'Lv', 'Ts', 'Og']
    return elements.index(el)



def to_molden(project: Project, vibrations_instance=-1, orbitals_instance=-1):
    nodes = project.xpath('//vibrations')
    if len(nodes) < 1 or vibrations_instance >= len(nodes) or vibrations_instance < -len(nodes):
        vibrations = False
        # anchor to orbitals instead
        nodes = project.xpath('//orbitals')
        if len(nodes) < 1 or orbitals_instance >= len(nodes) or orbitals_instance < -len(nodes): return None
        orbitals_node = nodes[orbitals_instance]
    else:
        vibrations = True
        anchor = nodes[vibrations_instance]
        nodes = project.xpath('//orbitals', anchor)
        orbitals_node = nodes[0] if len(
            nodes) > 0 else None  # assumes orbital calculation will be done right after vibrations
    geometry = project.xpath('//preceding::cml:atomArray', anchor)[-1]
    result = '[Molden Format]\n[Atoms] Angs\n'
    i = 0
    for atom in geometry:
        i += 1
        result += atom.get('elementType') + ' ' + str(i) + ' ' + str(
            atomic_number(atom.get('elementType'))) + ' ' + atom.get('x3') + ' ' + atom.get('y3') + ' ' + atom.get(
            'z3') + '\n'
    if vibrations:
        modes = list(reversed(project.xpath('normalCoordinate', anchor)))
        print('found', len(modes), 'normal coordinates')
        result += ' [FREQ]\n'
        for mode in modes:
            result += '    ' + str(mode.get('wavenumber')) + '\n'
        result += ' [FR-COORD]\n'
        for atom in geometry:
            result += atom.get('elementType') + ' ' + str(1.8897261246*float(atom.get('x3'))) + ' ' + str(1.8897261246*float(atom.get('y3'))) + ' ' + str(1.8897261246*float(atom.get( 'z3'))) + '\n'
        result += ' [FR-NORM-COORD]\n'
        i = 0
        for mode in modes:
            i += 1
            result += ' Vibration ' + str(i) + mode.text
        result += '[INT]\n'
        for mode in modes:
            result += '  ' + mode.get('IRintensity') + '\n'
    print(result)
    return result

# def vibrations_cjson(project: Project, instance=-1):
#     result = {'chemicalJson': 1}
#     nodes = project.xpath('//vibrations')
#     if len(nodes) < 1 or instance >= len(nodes) or instance < -len(nodes): return None
#     print(len(nodes))
#     print(nodes[instance])
#     modes = project.xpath('normalCoordinate', nodes[instance])
#     print('found', len(modes), 'normal coordinates')
#     geometry = project.xpath('//preceding::cml:atomArray', nodes[instance])[-1]
#     print('found', len(geometry), 'geometry')
#     result['atoms'] = {'coords': {'3d': []}, 'elements': {'number': []}}
#     for atom in geometry:
#         print(atom.get('x3'))
#         result['atoms']['coords']['3d'].append(atom.get('x3'))
#         result['atoms']['coords']['3d'].append(atom.get('y3'))
#         result['atoms']['coords']['3d'].append(atom.get('z3'))
#         # result['atoms']['elements'].
#     print(result)
#     import json
#     return json.dumps(result)


def launchExternalViewer(file):
    import subprocess
    try:
        viewer = 'jmol'
        subprocess.Popen([viewer, file])
    except:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Error")
        msg.setText('Cannot launch ' + viewer)
        msg.setInformativeText('Perhaps needs to be installed somewhere in $PATH?')
        msg.exec_()


