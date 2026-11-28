r"""Optional support for importing geometries from any file format Open Babel reads.

Open Babel is licensed under the GNU GPL v2, which is not compatible with iMolpro's
LGPL v3. It is therefore deliberately NOT imported into iMolpro's process (no
`from openbabel import pybel`): its command-line program `obabel` is run as a separate
process, so that iMolpro and Open Babel remain separate programs.

Open Babel is optional: if `obabel` cannot be found, only xyz files can be imported.

In a PyInstaller bundle, build.sh/build.ps1 copy `obabel` into `openbabel_bin`, its
format plugins into `openbabel_plugins` (on Windows, the top level of the bundle instead, next to
openbabel-3.dll), and its data files into `openbabel_data`; `obabel` is pointed at those with
BABEL_LIBDIR/BABEL_DATADIR (Open Babel otherwise looks in the prefix it was built for).
"""
import functools
import logging
import os
import pathlib
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

_TIMEOUT = 60  # seconds


def _bundle_directory():
    r"""Root of the PyInstaller bundle, or None if not running frozen"""
    return getattr(sys, '_MEIPASS', None)


@functools.lru_cache(maxsize=None)
def executable():
    r"""Path of the obabel program, or None if there isn't one"""
    base = _bundle_directory()
    if base is not None:
        bundled = os.path.join(base, 'openbabel_bin', 'obabel.exe' if os.name == 'nt' else 'obabel')
        if os.path.isfile(bundled):
            return bundled
    return shutil.which('obabel')


def _environment():
    environment = dict(os.environ)
    base = _bundle_directory()
    if base is not None:
        # obabel is in a subdirectory of the bundle, but the libraries it needs (and that its plugins
        # need) are collected at the top level. Unlike on macOS, where PyInstaller rewrites the library
        # paths, on Windows they are only found next to the program or on PATH.
        environment['PATH'] = base + os.pathsep + environment.get('PATH', '')
        # (On Windows BABEL_LIBDIR is ignored: obabel loads the plugins from the directory of openbabel-3.dll,
        # the top level of the bundle, where build.ps1 puts them.)
        for variable, directory in (('BABEL_LIBDIR', 'openbabel_plugins'), ('BABEL_DATADIR', 'openbabel_data')):
            path = os.path.join(base, directory)
            if os.path.isdir(path):
                environment[variable] = path
    return environment


def _run(arguments):
    kwargs = {}
    if os.name == 'nt':  # do not flash a console window from the windowed app
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    # stdin must be given explicitly: a windowed (no-console) frozen app has no valid stdin handle to inherit,
    # and on Windows CreateProcess then fails with WinError 50 / 6
    return subprocess.run([executable()] + arguments, capture_output=True, text=True, timeout=_TIMEOUT,
                          stdin=subprocess.DEVNULL, env=_environment(), **kwargs)


def available() -> bool:
    return executable() is not None


@functools.lru_cache(maxsize=None)
def suffixes() -> tuple:
    r"""File suffixes (without the dot) of the formats that can be read, xyz first."""
    result = ['xyz']
    if available():
        try:
            completed = _run(['-L', 'formats', 'read'])
            for line in completed.stdout.splitlines():
                if ' -- ' in line:
                    suffix = line.split(' -- ')[0].strip()
                    if suffix and suffix not in result:
                        result.append(suffix)
            if len(result) == 1:
                logger.warning('obabel (%s) listed no formats: exit code %s, stderr: %s', executable(),
                               completed.returncode, completed.stderr.strip())
        except (OSError, subprocess.SubprocessError):
            logger.exception('Could not list the formats obabel can read')
            return ('xyz',)
    return tuple(result[:1] + sorted(result[1:]))


def file_dialog_filter() -> str:
    return 'Geometry (' + ' '.join('*.' + s for s in suffixes()) + ')'


def to_xyz(filename, destination_directory) -> str:
    r"""Convert the first molecule in `filename` to an xyz file in `destination_directory`.

    :return: the path of the xyz file written, named after `filename` with suffix .xyz
    """
    if not available():
        raise RuntimeError('Open Babel (obabel) is not available, so only xyz files can be imported')
    path = pathlib.Path(filename).resolve()
    suffix = path.suffix[1:]
    if len(suffixes()) > 1 and suffix not in suffixes():
        raise ValueError(f'Open Babel cannot read files with suffix .{suffix}')
    # (if the list of formats could not be obtained, let obabel itself report what is wrong)
    result = pathlib.Path(destination_directory) / (path.stem + '.xyz')
    try:
        completed = _run([f'-i{suffix}', str(path), '-oxyz', '-O', str(result), '-f', '1', '-l', '1'])
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f'Could not run Open Babel ({executable()}): {e}') from e
    if completed.returncode != 0 or not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError(f'Open Babel could not convert the file (exit code {completed.returncode}): '
                           + (completed.stderr.strip() or 'no output'))
    return str(result)
