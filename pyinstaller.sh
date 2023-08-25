#!/bin/sh
if [ $(uname) = Darwin ]; then
  builddir=$TMPDIR/QtMolpro
  rm -rf $builddir
  pyinstaller --add-data JSmol.min.js:. --add-data jsmol:. --distpath $builddir/dist --windowed --osx-bundle-identifier=net.molpro.Qtmolpro --icon=/Applications/gmolpro.app/Contents/Resources/PQSMOL/data/molpro.icns  QtMolpro.py
  rm -rf $builddir/dist/QtMolpro
  cat <<EOF > $builddir/dist/QtMolpro.app/Contents/MacOS/qt.conf
[Paths]
Prefix = PyQt5/Qt/
EOF
  hdiutil create $builddir/QtMolpro.dmg -ov -volname 'QtMolpro' -fs HFS+ -srcfolder "$builddir/dist"
  rm -f QtMolpro.dmg
  hdiutil convert $builddir/QtMolpro.dmg -format UDZO -o QtMolpro.dmg
else
  pyinstaller QtMolpro.py
fi
