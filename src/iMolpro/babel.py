r"""Optional support for importing geometries from any file format Open Babel understands.

Open Babel is optional: if it cannot be imported, `available()` is False and only
xyz files can be imported.

In a PyInstaller bundle, Open Babel cannot find its format plugins and data files
by itself (it looks in the prefix it was built for). build.sh/build.ps1 therefore
copy them into the bundle under `openbabel_plugins` and `openbabel_data`, and
`_configure_frozen_environment()` points Open Babel at them before it is imported.
"""
import logging
import os
import pathlib
import sys

logger = logging.getLogger(__name__)


def _configure_frozen_environment():
    base = getattr(sys, '_MEIPASS', None)
    if base is None:
        return
    for variable, directory in (('BABEL_LIBDIR', 'openbabel_plugins'), ('BABEL_DATADIR', 'openbabel_data')):
        path = os.path.join(base, directory)
        if os.path.isdir(path):
            os.environ.setdefault(variable, path)


_configure_frozen_environment()
try:
    from openbabel import pybel
except ImportError:
    pybel = None
    logger.info('openbabel is not installed: only xyz geometry files can be imported')


def available() -> bool:
    return pybel is not None


def suffixes() -> list:
    r"""File suffixes (without the dot) of the formats that can be read, xyz first."""
    if not available():
        return ['xyz']
    return ['xyz'] + sorted(s for s in pybel.informats if s != 'xyz')


def file_dialog_filter() -> str:
    return 'Geometry (' + ' '.join('*.' + s for s in suffixes()) + ')'


def to_xyz(filename, destination_directory) -> str:
    r"""Convert the first molecule in `filename` to an xyz file in `destination_directory`.

    :return: the path of the xyz file written, named after `filename` with suffix .xyz
    """
    if not available():
        raise RuntimeError('Open Babel is not available, so only xyz files can be imported')
    path = pathlib.Path(filename)
    suffix = path.suffix[1:]
    if suffix not in pybel.informats:
        raise ValueError(f'Open Babel cannot read files with suffix .{suffix}')
    molecule = next(pybel.readfile(suffix, str(path)))
    result = pathlib.Path(destination_directory) / (path.stem + '.xyz')
    result.write_text(molecule.write('xyz'))
    return str(result)
