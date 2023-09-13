#!/bin/sh

if [ $(uname) = Darwin ]; then
  brew install qt@5 create-dmg
else
  echo 'make sure Qt5 C++ libraries are installed'
fi
conda install -c conda-forge -y pymolpro
pip3 install pyqt5 --config-settings --confirm-license= --verbose
pip install pyinstaller PyQtWebEngine


if [ $(uname) = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.Molpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/Molpro
rm -rf $builddir

PATH=/usr/bin:$PATH pyinstaller \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  --distpath $builddir/dist $pyinstaller_opt \
  Molpro.py || exit 1

if [ $(uname) = Darwin ]; then
  rm -rf $builddir/dist/Molpro
  rm -f Molpro.dmg
  create-dmg --app-drop-link 25 35 --volname Molpro  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' Molpro.dmg "$builddir/dist"
else
  rm -rf dist build
  mv $builddir/dist .
fi
