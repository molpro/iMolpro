#!/usr/bin/env python3
"""
Regenerate the conda-syntax requirements file used by build.sh/build.ps1
from this package's own pyproject.toml, so iMolpro's Python runtime
dependencies only ever need to be edited in one place.

conda's MatchSpec parser accepts plain PEP 508 version constraints (e.g.
"pysjef>=1.45.11") directly -- no reformatting needed -- so this just
copies pyproject.toml's [project.dependencies] list out verbatim, one
requirement per line. See CEP 29 (the MatchSpec spec): an operator such
as >=, <, == unambiguously marks where the version field starts, so no
space before it is required.

Build-only tooling that conda needs but that isn't a runtime dependency
of iMolpro itself (pyinstaller, git, certifi, openssl, ...) intentionally
lives in conda-build-tools.txt instead, not here: that's a different
concern (what the *build environment* needs) from this one (what
iMolpro's own code imports), and folding it into pyproject.toml's
dependency list would make `pip install iMolpro` pull in build tooling
that a normal user has no use for.

Usage: generate_conda_requirements.py [output_path]
       (defaults to stdout)
"""
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]

    lines = [
        "# Generated from pyproject.toml by scripts/generate_conda_requirements.py.",
        "# Do not edit by hand -- edit [project.dependencies] in pyproject.toml",
        "# instead, then rerun this script (build.sh / build.ps1 do this",
        "# automatically, so this file does not need to be committed).",
        *dependencies,
    ]
    text = "\n".join(lines) + "\n"

    if len(sys.argv) > 1:
        pathlib.Path(sys.argv[1]).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
