## iMolpro

This app provides an integrated environment for the Molpro quantum chemistry package.  You can prepare inputs for jobs, launch them, and view their results.

The program works with Molpro *Projects* that are managed by [sjef](https://github.com/molpro/sjef/blob/master/README.md). Each sjef project is a filesystem directory with suffix `.molpro` that contains all files associated with the job, together with some status information.  This program allows you to create new projects, and also to work with existing projects that might have been created elsewhere (for example, with [pymolpro](https://github.com/molpro/pymolpro/blob/master/README.rst), or [gmolpro](https://www.molpro.net/manual/doku.php?id=gmolpro_graphical_user_interface)).

On launching, you will normally see the Chooser window that allows you to open or create projects. You can have as many open as you want, and each appears in its own independent project window.  Each project window has two principal panes: on the left is the job input, either as the actual Molpro input file or via a menu-driven guided input creator; on the right is the job output and/or the three-dimensional molecular structure together with any orbitals or vibrational modes that have been calculated, and an editable three-dimensional model of the input geometry. See [here](doc/example.md) for more details.

Molecular structures can be prepared and edited within the program, or imported from an external database search ([PubChem](https://pubchem.ncbi.nlm.nih.gov) or [ChemSpider](https://www.chemspider.com)). On opening a new project, you are prompted first of all to import a local file, or if declined, a database search, but if preferred the geometry can simply be edited directly into the input, or in the embedded structure editor. Geometry import can be carried out at any later stage also.

Once the input has been prepared, the job can be submitted either locally (default) or remotely (via a configured sjef backend). The sjef backend specifications can be edited from the program. Once running, the job status and output are monitored and displayed continuously.

Editing of input can be done in one of _guided_ or _freehand_ modes. In guided mode, the default for new projects, as well for old inputs that are sufficiently simple that their structure can be parsed, methods and options are specified through buttons and menus. In freehand mode, the text of the input is simply edited by hand. It is possible at any time to toggle between the two modes, and if guided mode becomes impossible, an attempt to toggle will show information on why. Most projects prepared previously with
[gmolpro](https://www.molpro.net/manual/doku.php?id=gmolpro_graphical_user_interface) will open successfully in guided mode.
### License
iMolpro is licensed under the [GNU GPL v3](https://www.gnu.org/licenses/licenses.html#GPL).
### Acknowledgements
The following libraries are used.

* [PyQt5](https://riverbankcomputing.com/software/pyqt/intro), a set of Python bindings for [The Qt Company](https://www.qt.io/)'s Qt application framework,
licensed under the [GNU GPL v3](https://www.gnu.org/licenses/licenses.html#GPL).
* [Jmol](http://www.jmol.org/), an open-source Java viewer for chemical structures in 3D, licensed under the [GNU LGPL](https://www.gnu.org/licenses/licenses.html#LGPL).
* [PyInstaller](https://pyinstaller.org/)
* [pysjef](https://github.com/molpro/pysjef)
* [pymolpro](https://github.com/molpro/pymolpro)
* [PubChemPy](https://github.com/mcs07/PubChemPy), licensed under the MIT license.
* [ChemSpiPy](https://github.com/mcs07/ChemSpiPy), licensed under the MIT license.
