## iMolpro

This app provides an integrated environment for the [Molpro](https://www.molpro.net) quantum chemistry package.  You can prepare inputs for jobs, launch them, and view their results.

The program works with Molpro *Projects* that are managed by [sjef](https://github.com/molpro/sjef/blob/master/README.md). Each sjef project is a filesystem directory with suffix `.molpro` that contains all files associated with the job, together with some status information.  This program allows you to create new projects, and also to work with existing projects that might have been created elsewhere (for example, with [pymolpro](https://github.com/molpro/pymolpro/blob/master/README.rst), or [gmolpro](https://www.molpro.net/manual/doku.php?id=gmolpro_graphical_user_interface)).

iMolpro requires a full copy of Molpro installed locally to be fully useful. However, it includes an embedded reduced-functionality  version of Molpro which will be used if full Molpro cannot be found. The embedded molpro is restricted in the size of problem, kind of calculation, and execution time, and may be used for educational and evaluation purposes only.

