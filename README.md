## iMolpro

This app provides an integrated environment for the Molpro quantum chemistry package.  You can prepare inputs for jobs, launch them, and view their results.

The program works with Molpro *Projects* that are managed by [sjef](https://github.com/molpro/sjef/blob/master/README.md). Each sjef project is a filesystem directory with suffix `.molpro` that contains all files associated with the job, together with some status information.  This program allows you to create new projects, and also to work with existing projects that might have been created elsewhere (for example, with [pymolpro](https://github.com/molpro/pymolpro/blob/master/README.rst), or [gmolpro](https://www.molpro.net/manual/doku.php?id=gmolpro_graphical_user_interface)).

On launching, you will normally see the Chooser window that allows you to open or create projects. You can have as many open as you want, and each appears in its own independent project window.  Each project window has two principal panes: on the left is the job input, either as the actual Molpro input file or via a menu-driven guided input creator; on the right is the job output and/or the three-dimensional molecular structure together with any orbitals or vibrational modes that have been calculated, and an editable three-dimensional model of the input geometry.
See [here](doc/runs.md) for more details,
and [here](doc/example.md) for discussion of an example work flow.

It is also possible to bring in previously-prepared Molpro input files (with suffix `.inp`), or Molpro output files (suffix `.out`). They can be selected instead of a project on the command line, or in the Open dialogue. Then a project is created in the same directory as the file if possible, or a temporary directory if not, and the file copied in. If the file is an output file, an attempt will be made to reconstruct and include the corresponding input file.

Molecular structures can be prepared and edited within the program, or imported from an external database search ([PubChem](https://pubchem.ncbi.nlm.nih.gov) or [ChemSpider](https://www.chemspider.com)). On opening a new project, you are prompted first of all to import a local file, or if declined, a database search, but if preferred the geometry can simply be edited directly into the input, or in the embedded structure editor. Geometry import can be carried out at any later stage also.

Once the input has been prepared, the job can be submitted either locally (default) or remotely (via a configured sjef backend). The sjef backend specifications can be edited from the program. Once running, the job status and output are monitored and displayed continuously.

Editing of input can be done in one of _guided_ or _freehand_ modes. In guided mode, the default for new projects, as well for old inputs that are sufficiently simple that their structure can be parsed, methods and options are specified through buttons and menus. In freehand mode, the text of the input is simply edited by hand. It is possible at any time to toggle between the two modes, and if guided mode becomes impossible, an attempt to toggle will show information on why. Most projects prepared previously with
[gmolpro](https://www.molpro.net/manual/doku.php?id=gmolpro_graphical_user_interface) will open successfully in guided mode.
### Installation
Binaries prepared with [PyInstaller](https://pyinstaller.org/) are available for Windows, macOS, and Linux, and can be downloaded from the [releases](https://github.com/molpro/imolpro/releases) page.
The package is alternatively available as a Python module published on [PyPI](https://pypi.org/project/iMolpro/), and can be installed with `pip install iMolpro`, which has the effect of providing the command `iMolpro` in the current Python environment.

In the case of MacOS, the PyInstaller-built binary is an application bundle which, when normally installed in `/Applications`, registers as an opener for Molpro projects, which means that you can double-click on a Molpro project file to launch iMolpro. To also be able to launch iMolpro (optionally with a project, input, or output file as argument) from Terminal, use the `iMolpro > Install command line tool...` menu item; this installs an `iMolpro` command at `/usr/local/bin/iMolpro`, prompting for an administrator password if needed, and the same menu item can be used afterwards to reinstall or remove it again.
### License
iMolpro is
licensed under the [GNU LGPL v3](https://opensource.org/license/lgpl-3-0).
### Acknowledgements
The following libraries are used.

* [PySide6](https://doc.qt.io/qtforpython-6/), a set of Python bindings for [The Qt Company](https://www.qt.io/)'s Qt application framework,
licensed under the [GNU LGPL v3](https://opensource.org/license/lgpl-3-0).
* [VTK](https://vtk.org/), a software system for 3D computer graphics, image processing and visualization, licensed under the [BSD 3-Clause License](https://opensource.org/license/bsd-3-clause/).
* [PyInstaller](https://pyinstaller.org/)
* [pysjef](https://github.com/molpro/pysjef)
* [pymolpro](https://github.com/molpro/pymolpro)
* [PubChemPy](https://github.com/mcs07/PubChemPy), licensed under the MIT license.
* [ChemSpiPy](https://github.com/mcs07/ChemSpiPy), licensed under the MIT license.
* [DraggableTabWidget](https://github.com/akihito-takeuchi/qt-draggable-tab-widget), licensed under the MIT license.
