#!/bin/sh

conda install -c conda-forge -y --file=requirements.txt python=3.12 scipy=1.11  || exit 1
conda remove -y pubchempy
pip install --force-reinstall https://github.com/molpro/PubChemPy/archive/refs/heads/master.zip
conda list

#if [ "$(uname)" = Darwin -a $(uname -m) = x86_64 ]; then
#  conda install -c conda-forge -y scipy==1.11
#fi

if [ "$(uname)" = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.iMolpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/iMolpro
rm -rf "${builddir}"

versionfile=${TMPDIR:-/tmp}/VERSION
git config --global --add safe.directory "$PWD"
version=$(git describe --tags --dirty --always)
echo "$version" > "${versionfile}"

PATH=/usr/bin:$PATH pyi-makespec \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  --add-data "${versionfile}":. \
  $pyinstaller_opt \
  iMolpro.py || exit 1
sed -i -e '$d' iMolpro.spec
cat << 'EOF' >> iMolpro.spec
    info_plist={
      'NSPrincipalClass' : 'NSApplication',
      'NSHighResolutionCapable' : 'True',
      'CFBundleDocumentTypes': [
        {
          'CFBundleTypeExtensions': ['molpro'],
          'LSTypeIsPackage': True,
          'CFBundleTypeIconFile': 'molpro.icns',
          'CFBundleTypeRole': 'Editor',
          'CFBundleTypeName': 'Molpro Project'
        }
      ]
    }
)
EOF
PATH=/usr/bin:$PATH pyinstaller \
  --distpath "${builddir}"/dist \
  iMolpro.spec || exit 1

descriptor=${version}.$(uname).$(uname -m)
if [ "$(uname)" = Darwin ]; then
  (cd "${builddir}"/dist/iMolpro.app/Contents/Resources||exit 1; for i in PyQt5/Qt/resources/* ; do ln -s "$i" . ; done)
  (cd "${builddir}"/dist/iMolpro.app/Contents||exit 1; ln -s MacOS/Resources/PyQt5/Qt/translations .)
  rm -rf "${builddir}"/dist/iMolpro
  cp -p doc/INSTALL_macOS_binary.md "${builddir}"/dist/INSTALL
  (cd "${builddir}"/dist||exit 1; ln -s /Applications .)
  rm -f iMolpro-"${descriptor}".dmg
  if [ -r /Volumes/iMolpro-"${descriptor}" ]; then umount /Volumes/iMolpro-"${descriptor}" ; fi
  rm -rf dist
  mkdir -p dist
  ls -lR dist
#  create-dmg --app-drop-link 25 35 --volname iMolpro-"${descriptor}"  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' dist/iMolpro-"${descriptor}".dmg "${builddir}"/dist
  hdiutil create ./iMolpro.dmg -ov -fs HFS+ -srcfolder "${builddir}"/dist
  echo after first hdiutil
  hdiutil convert ./iMolpro.dmg -format UDZO -o dist/iMolpro-"${descriptor}".dmg
  cp Molpro_Logo_Molpro_Quantum_Chemistry_Software.png "${builddir}"
  (cd "${builddir}" && sips -i Molpro_Logo_Molpro_Quantum_Chemistry_Software.png && DeRez -only icns Molpro_Logo_Molpro_Quantum_Chemistry_Software.png > tmp.rsrc)
  Rez -append "${builddir}"/tmp.rsrc -o dist/iMolpro-"${descriptor}".dmg
  SetFile -a C dist/iMolpro-"${descriptor}".dmg
  rm ./iMolpro.dmg
else
  rm -rf dist build
  mv "${builddir}"/dist .
  tar cjf dist/iMolpro-"${descriptor}".tar.bz2 -C dist iMolpro
fi
