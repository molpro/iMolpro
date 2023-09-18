#!/bin/sh

if [ $(uname) = Darwin ]; then
  which create-dmg > /dev/null || brew install create-dmg
  if [ -r /Volumes/Molpro ]; then umount /Volumes/Molpro ; fi
fi
conda install -c conda-forge -y pyqt pyqtwebengine pyinstaller pymolpro || exit 1


if [ $(uname) = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.Molpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/Molpro
rm -rf $builddir

PATH=/usr/bin:$PATH pyi-makespec \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  $pyinstaller_opt \
  Molpro.py || exit 1
sed -i -e '$d' Molpro.spec
cat << 'EOF' >> Molpro.spec
    info_plist={
      'CFBundleDocumentTypes': [
        {
          'CFBundleTypeExtensions': ['molpro'],
          'LSItemContentTypes': ['net.molpro.molpro'],
          'CFBundleTypeIconFile': 'molpro.icns',
          'CFBundleTypeRole': 'Editor',
          'CFBundleTypeName': 'Molpro Project'
        }
      ]
    }
)
EOF
PATH=/usr/bin:$PATH pyinstaller \
  --distpath $builddir/dist \
  Molpro.spec || exit 1

if [ $(uname) = Darwin ]; then
  cp -p $builddir/dist/Molpro.app/Contents/MacOS/PyQt5/Qt/resources/* $builddir/dist/Molpro.app/Contents/Resources
  cp -pr $builddir/dist/Molpro.app/Contents/MacOS/PyQt5/Qt/translations $builddir/dist/Molpro.app/Contents/
  rm -rf $builddir/dist/Molpro
  rm -f Molpro.dmg
  create-dmg --app-drop-link 25 35 --volname Molpro  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' Molpro-$(uname)-$(uname -m).dmg "$builddir/dist"
else
  rm -rf dist build
  mv $builddir/dist .
  tar cjf Molpro-$(uname)-$(uname -m).tar.bz2 -C dist Molpro
fi
