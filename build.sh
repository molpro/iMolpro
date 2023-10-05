#!/bin/sh

conda install -c conda-forge -y --file=requirements.txt  || exit 1


if [ $(uname) = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.iMolpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/iMolpro
rm -rf $builddir

versionfile=${TMPDIR:-/tmp}/VERSION
git config --global --add safe.directory $PWD
version=$(git describe --tags --dirty --always)
echo $version > ${versionfile}

PATH=/usr/bin:$PATH pyi-makespec \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  --add-data ${versionfile}:. \
  $pyinstaller_opt \
  iMolpro.py || exit 1
sed -i -e '$d' iMolpro.spec
cat << 'EOF' >> iMolpro.spec
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
  iMolpro.spec || exit 1

descriptor=${version}.$(uname).$(uname -m)
if [ $(uname) = Darwin ]; then
  (cd $builddir/dist/iMolpro.app/Contents/Resources; for i in PyQt5/Qt/resources/* ; do ln -s $i . ; done)
  (cd $builddir/dist/iMolpro.app/Contents; ln -s MacOS/Resources/PyQt5/Qt/translations .)
  rm -rf $builddir/dist/iMolpro
  (cd $builddir/dist; ln -s /Applications .)
  rm -f iMolpro-${descriptor}.dmg
  if [ -r /Volumes/iMolpro-${descriptor} ]; then umount /Volumes/iMolpro-${descriptor} ; fi
  rm -rf dist
  mkdir -p dist
#  create-dmg --app-drop-link 25 35 --volname iMolpro-${descriptor}  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' dist/iMolpro-${descriptor}.dmg "$builddir/dist"
  ls -l $builddir/dist
  du -hd2 $builddir/dist
  hdiutil create -verbose ./iMolpro.dmg -ov -fs HFS+ -srcfolder "$builddir/dist"
  hdiutil convert -verbose ./iMolpro.dmg -format UDZO -o dist/iMolpro-${descriptor}.dmg
  cp Molpro_Logo_Molpro_Quantum_Chemistry_Software.png $builddir
  (cd $builddir && sips -i Molpro_Logo_Molpro_Quantum_Chemistry_Software.png && DeRez -only icns Molpro_Logo_Molpro_Quantum_Chemistry_Software.png > tmp.rsrc)
  Rez -append $builddir/tmp.rsrc -o dist/iMolpro-${descriptor}.dmg
  SetFile -a C dist/iMolpro-${descriptor}.dmg
  rm ./iMolpro.dmg
else
  rm -rf dist build
  mv $builddir/dist .
  tar cjf dist/iMolpro-${descriptor}.tar.bz2 -C dist iMolpro
fi
