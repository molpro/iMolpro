#!/usr/bin/env python
"""
Thin launcher for iMolpro.

The application itself lives in the ``iMolpro`` package under ``src/``
(src-layout). This script exists so that:

* ``python iMolpro.py`` keeps working from a plain source checkout, with no
  install step required (it puts ``src/`` at the front of ``sys.path`` so the
  real ``iMolpro`` package is found before this file's own name could ever be
  mistaken for it).
* PyInstaller (see build.sh / build.ps1) has a top-level entry-point script
  to analyse and bundle, as it always has; when frozen, PyInstaller's own
  import machinery finds the bundled ``iMolpro`` package directly and there
  is no ``src`` directory on disk to worry about.

For a normal development install, prefer ``pip install -e .`` followed by
``python -m iMolpro`` or the ``iMolpro`` console-script.
"""
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent / 'src'
if _src.is_dir():
    sys.path.insert(0, str(_src))

from iMolpro.__main__ import main

if __name__ == '__main__':
    main()
