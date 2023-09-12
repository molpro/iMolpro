#!/bin/sh

if [ $(uname) = Darwin ]; then
  brew install qt@5
else
  echo 'make sure Qt5 C++ libraries are installed'
fi
conda install -c conda-forge -y pymolpro
pip3 install pyqt5 --config-settings --confirm-license= --verbose
pip install pyinstaller PyQtWebEngine


if [ $(uname) = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.Qtmolpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/QtMolpro
rm -rf $builddir

pyinstaller \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --distpath $builddir/dist $pyinstaller_opt \
  QtMolpro.py

if [ $(uname) = Darwin ]; then
  rm -rf $builddir/dist/QtMolpro
  hdiutil create $builddir/QtMolpro.dmg -ov -volname 'QtMolpro' -fs HFS+ -srcfolder "$builddir/dist"
  rm -f QtMolpro.dmg
  hdiutil convert $builddir/QtMolpro.dmg -format UDZO -o QtMolpro.dmg
else
  rm -rf dist build
  mv $builddir/dist .
fi
