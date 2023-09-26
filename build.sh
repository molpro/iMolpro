#!/bin/sh

if [ $(uname) = Darwin ]; then
  which create-dmg > /dev/null || brew install create-dmg
fi
conda install -c conda-forge -y pyqt pyqtwebengine pyinstaller pymolpro pubchempy chemspipy openbabel || exit 1


if [ $(uname) = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.Molpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/Molpro
rm -rf $builddir

versionfile=${TMPDIR:-/tmp}/VERSION
version=$(git describe --tags --dirty)
echo $version > ${versionfile}

PATH=/usr/bin:$PATH pyi-makespec \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  --add-data ${versionfile}:. \
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

descriptor=${version}.$(uname).$(uname -m)
if [ $(uname) = Darwin ]; then
  (cd $builddir/dist/Molpro.app/Contents/Resources; for i in PyQt5/Qt/resources/* ; do ln -s $i . ; done)
  (cd $builddir/dist/Molpro.app/Contents; ln -s MacOS/Resources/PyQt5/Qt/translations .)
  rm -rf $builddir/dist/Molpro
  rm -f Molpro-${descriptor}.dmg
  if [ -r /Volumes/Molpro-${descriptor} ]; then umount /Volumes/Molpro-${descriptor} ; fi
  rm -rf dist
  mkdir -p dist
  create-dmg --app-drop-link 25 35 --volname Molpro-${descriptor}  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' dist/Molpro-${descriptor}.dmg "$builddir/dist"
else
  rm -rf dist build
  mv $builddir/dist .
  tar cjf dist/Molpro-${descriptor}.tar.bz2 -C dist Molpro
fi
