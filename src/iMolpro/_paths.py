"""
Resolve the directory containing iMolpro's bundled, non-package data files
(README.md, doc/, the Molpro logo, etc).

These files live in ``src/iMolpro/data`` so that they are actually part of
the installable ``iMolpro`` package (setuptools only ships files that live
*inside* the package directory; anything at the repository root, such as
this used to be laid out, is silently invisible to a real ``pip install``
regardless of any package-data declaration).

Two cases:

* Frozen (PyInstaller): the data files are unpacked directly to
  ``sys._MEIPASS`` by the ``--add-data ...:.`` options in
  build.sh/build.ps1 (which now point at ``src/iMolpro/data/...`` as their
  source, but still install to the bundle root), unchanged.
* Not frozen (running from a source checkout, an editable install, or a
  real installed package/wheel): resolved via ``importlib.resources``
  relative to the installed ``iMolpro`` package itself, rather than via a
  ``__file__``-relative parent-directory count. The old
  ``Path(__file__).resolve().parents[2]`` approach happened to work for a
  source checkout (and, by coincidence, for an editable install, since
  ``__file__`` there still points into the checkout) but silently resolved
  to a meaningless path for a real, non-editable installed package -- e.g.
  ``<venv>/lib/python3.13`` -- which is what caused the Molpro logo (and
  everything else previously kept at the repo root) to go missing for a
  plain ``pip install iMolpro``.
"""
import pathlib
import sys
from importlib.resources import files


def app_root() -> pathlib.Path:
    """Directory containing iMolpro's bundled data files."""
    if hasattr(sys, '_MEIPASS'):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(str(files('iMolpro') / 'data'))
