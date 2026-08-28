import os
import subprocess

from ._paths import app_root

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # pragma: no cover - Python < 3.8
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version('iMolpro')
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled checkout
    __version__ = 'unknown'


def full_version() -> str:
    """
    iMolpro's version, preferring a live ``git describe`` of a source
    checkout (so a dev build shows how far it is past the last tag),
    then falling back to a bundled VERSION file, then to the installed
    package metadata (``__version__``).
    """
    if os.path.exists(app_root() / '.git'):
        try:
            described = subprocess.check_output(
                ['git', '-C', str(app_root()), 'describe', '--tags', '--dirty']).decode('ascii').strip()
            if described:
                return described
        except Exception:
            pass
    version_file = app_root() / 'VERSION'
    if os.path.exists(version_file):
        content = open(version_file, 'r').read().strip()
        if content:
            return content
    return __version__
