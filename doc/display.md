## Display of molecular structure and properties

Whenever possible, the program will present one or more interactive three-dimensional model of 
the molecule, which are embedded instances of the  [Jmol](http://www.jmol.org/) structure viewer. The different types of model that can appear, depending on job type, include
- `builder`. The xyz file containing the input geometry, if the geometry is specified with a file reference rather than inline. Jmol contains some basic editing capabilities that allow the molecular structure to be changed. They can be accessed by clicking near the top left corner of the editing pane, and then clicking the `Save` button to commit the changed structure.
- `initial structure`. The actual computed input geometry, evaluated by running Molpro. This allows inline geometries, possibly in Z-matrix format, to be viewed but not edited.
- `final structure`. The final structure after any geometry optimisation, together with animated normal vibrational modes if these have been computed.
- `Canonical`, `Intrinsic Bond`,.... If requested in the input, then three-dimensional orbital contours are presented. Some controls are presented; further options are available through raw Jmol commands.


The full Jmol menu is available, together with an box that accepts any [Jmol scripting command](https://chemapps.stolaf.edu/jmol/docs), and together these allow finer control of the display, as well as the export of images.