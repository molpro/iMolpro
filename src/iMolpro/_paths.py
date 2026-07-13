"""
Resolve the directory containing iMolpro's bundled, non-package data files
(JSmol.min.js, j2s/, README.md, doc/, the Molpro logo, etc).

Historically all of iMolpro's Python modules lived flat in the repository
root, next to these data files, so ``pathlib.Path(__file__).parent`` was
enough to find them both when running from source and when frozen by
PyInstaller (which also placed the entry-point module at the bundle root).

Now that the code lives in a ``src/iMolpro`` package, ``__file__`` no longer
sits next to the data files, so this helper centralises the two cases:

* Frozen (PyInstaller): the data files are unpacked to ``sys._MEIPASS`` by
  the ``--add-data ...:.`` options in build.sh/build.ps1, unchanged.
* Running from a source checkout: the data files remain at the repository
  root, two levels above this file (``<repo>/src/iMolpro/_paths.py``).
"""
import pathlib
import sys


def app_root() -> pathlib.Path:
    """Directory containing iMolpro's bundled data files."""
    if hasattr(sys, '_MEIPASS'):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).resolve().parents[2]
