# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

iMolpro is a desktop GUI (PySide6/Qt + VTK) for the Molpro quantum chemistry package. It creates/edits/monitors Molpro *Projects* (filesystem directories with suffix `.molpro`), which are actually managed by the external `pysjef`/`pymolpro` packages, not by this repo — iMolpro is a presentation layer over those. It ships three ways: a PyInstaller-frozen native app (macOS/Linux/Windows), a `pip install iMolpro` package (PyPI), and, in the frozen build, bundled together with a reduced "teach" copy of Molpro itself.

## Commands

Run from a source checkout (repo root, with `src/` on the path via `pyproject.toml`'s `pythonpath`):

```sh
python -m pytest                          # run all tests
python -m pytest tests/test_utilities.py   # single file
python -m pytest tests/test_utilities.py::test_basic_mapping_operations  # single test
```

Tests use `pytest-qt` (the `qtbot` fixture, e.g. `tests/EditFile_test.py`). It is not declared anywhere in `pyproject.toml` — the only place it's installed is the `Dockerfile`, which also references a root-level `requirements.txt` that no longer exists in the repo (conda requirements are now generated on the fly by `scripts/generate_conda_requirements.py`). Install `pytest-qt` manually if it's missing from your environment, and GUI tests need a display (or `QT_QPA_PLATFORM=offscreen`/Xvfb) to run headless.

Run the app from source:

```sh
python iMolpro.py          # repo-root launcher script
# or, once installed / in editable mode:
python -m iMolpro
```

Build a standalone distributable (PyInstaller, requires conda):

```sh
sh ./build.sh       # macOS / Linux, output in dist/
./build.ps1         # Windows
```

`build.sh`/`build.ps1` regenerate conda-syntax requirements from `pyproject.toml` via `scripts/generate_conda_requirements.py` before installing — `pyproject.toml`'s `[project.dependencies]` is the single source of truth for iMolpro's runtime dependencies; `conda-build-tools.txt` is only for build-time tooling (pyinstaller, git, certifi, openssl) and is edited by hand.

There is no lint config and no CI test workflow (`.github/workflows/` only has `deploy.yml`, `publish-pypi.yml`, `tag-latest.yml`, `clean-releases.yml` — deploy builds run `build.sh`/`build.ps1` directly, no `pytest` step).

Package version comes from git tags via `setuptools_scm` (see the comment block in `pyproject.toml` about `tag.strict` — the repo has non-version tags like `latest_2026_05_06_<hash>` that must be excluded from `git describe`).

Pushing to any branch with "candidate" in its name (matching *candidate*) triggers deploy.yml, which does a full signed and notarized macOS/Windows build and uploads release artifacts — not just a CI check. Don't use that naming pattern for a branch you don't intend to trigger a real release build from. It's there to allow a developer to test the release workflow without having to push to `master`.

## Architecture

**Qt binding indirection.** Nearly every UI module (`Chooser.py`, `ProjectWindow.py`, `MenuBar.py`, `backend.py`, `WindowManager.py`, etc.) imports Qt via a repeated `try: from PySide6... except ImportError: try: from PyQt6... except ImportError: from PyQt5...` chain, and often follows it with enum-compatibility shims (Qt5 flat enums like `Qt.AlignCenter` vs Qt6 scoped ones like `Qt.AlignmentFlag.AlignCenter`). `pyqt_discover.py` does the analogous binding detection for VTK's Qt interactor. When editing UI code, preserve this fallback pattern rather than importing one binding directly — PySide6 is primary but PyQt6/PyQt5 must keep working.

**Window/app lifecycle.** `__main__.py:main()` builds a `QApplication` subclass that turns OS file-open events (`.molpro`/`.out`/`.inp`/`.xml`) into new windows, then constructs one `WindowManager` for the process. `WindowManager` (`WindowManager.py`) tracks all open top-level windows, shows the `Chooser` when none are open and hides it once one is, and owns the single shared "Install command line tool..." `QAction` — moved between whichever window's menu bar is currently active rather than duplicated, because Qt's macOS menu-merging dedupes by action identity, not by active window (see the long comment in `set_cli_action_owner`).

**Two window types:**
- `Chooser` (`Chooser.py`) — the launcher: open/create/recent-projects list.
- `ProjectWindow` (`ProjectWindow.py`, the largest file, ~1800 lines) — one per open project. Left pane is job input, either freehand text (`GuidedPane`/`EditFile`-style editors) or the guided, menu-driven builder; right pane is output text plus the VTK 3D view (structure, orbitals, vibrational modes). Input editing toggles between *guided* mode (buttons/menus, used when the input is simple enough to parse) and *freehand* mode (raw text); guided mode is unavailable for inputs it can't parse, and the module explains why when a toggle attempt fails.

**Domain/project layer.** `project.py`'s `Project` subclasses `pymolpro.Project` and adds iMolpro-specific conveniences (`filename()` defaulting to the current run directory, `run_directory_names`, `structure()` which parses the Molpro XML output — or, if frequencies are requested, delegates to `VibrationSetXML` — into a `Structure(atoms, vibrations)` dataclass). Actual job submission/monitoring and backend definitions live in the external `pysjef`/`pymolpro` packages; `backend.py` is just the dialog for editing a project's chosen sjef backend (local vs. remote) and its parameters.

**3D rendering.** `vtk_molecule_widget.py` (~1100 lines) and `QVTKRenderWindowInteractor.py` implement the molecule viewer on top of VTK: custom actors for nuclei (`NucleiActor`), bonds (`BondActor`/`BondActorCollection`), labels, and volumetric orbital/density data (`CubeActor`, `create_vtk_image_data`, `cube_data.py`). `MoleculeWidget`/`MoleculeScene`/`ControlPanel` compose these into the interactive panel embedded in `ProjectWindow`.

**Parsing utilities.** `utilities.py` (~650 lines) is the shared grab-bag: `EditFile`/`QVimPlainTextEdit` (a text editor widget with vim-mode keybindings) and `ViewFile` for output viewing; a factory-dispatch trio — `factory_coordinate_set`, `factory_orbital_set`, `factory_vibration_set` — each picking a Molden- or XML-backed implementation class based on `file_type`; and `FileBackedDictionary`, a `MutableMapping` that persists to JSON, used for both app settings and (indirectly) project state.

**Settings & data files.** `settings.py` exposes a single module-level `settings` (`FileBackedDictionary` at `~/.molpro/iMolpro.settings.json`) plus `settings_edit()`, which builds its dialog from `OptionsDialog`. `_paths.py` resolves iMolpro's bundled non-code assets (`data/` — logo, `doc/*.md`); it deliberately does *not* use a `__file__`-relative parent count, because that silently breaks for a real (non-editable) installed package. Assets must live under `src/iMolpro/data/` — anything at the repo root is invisible to a real `pip install` regardless of `package-data` config — and are resolved via `importlib.resources` when not frozen, or `sys._MEIPASS` when running as a PyInstaller bundle.

**CLI install feature.** `cli_install.py`/`cli_install_ui.py` implement the macOS-only "Install command line tool..." feature, which drops an `iMolpro` wrapper script at `/usr/local/bin/iMolpro` (prompting for a privileged write if needed) when running as a frozen `.app` bundle. `WindowManager` owns the single shared action for this (see above).

**Platform quirks worth knowing before touching `__main__.py`:** on Linux, `QT_QPA_PLATFORM` is forced to `xcb` (not native Wayland) because VTK's X11-based renderer can't get a window handle under Wayland; on Windows, `PATH`/`CONDA_PREFIX` are patched so a frozen build can find Molpro and conda tooling; on non-Windows, `PATH` is re-derived from a login shell so GUI-launched processes see the same `PATH` a terminal would.
