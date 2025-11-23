#!/bin/sh

#pkgbuild=1
dmg=1
#tar=1
sh=1

if [ -z "$NOCONDA" ]; then
#conda install -c conda-forge -c defaults -y --file=requirements.txt python=3.12 scipy=1.11  || exit 1
#conda remove -y pubchempy
#pip install -I https://github.com/molpro/PubChemPy/archive/refs/heads/main.zip
conda install -c conda-forge -c defaults -y --file=requirements.txt || exit
gem install --user-install -n~/bin fpm
PATH=~/bin:$PATH
#conda list
fi

#if [ "$(uname)" = Darwin -a $(uname -m) = x86_64 ]; then
#  conda install -c conda-forge -y scipy==1.11
#fi

. ./ENV

if [ "$(uname)" = Darwin ]; then
  pyinstaller_opt="--windowed --osx-bundle-identifier=net.molpro.iMolpro --icon=molpro.icns"
fi
builddir=${TMPDIR:-/tmp}/iMolpro
rm -rf "${builddir}"

versionfile=${TMPDIR:-/tmp}/VERSION
git config --global --add safe.directory "$PWD"
version=$(git describe --tags --dirty --always)
echo "$version" > "${versionfile}"

echo molpro_version=$molpro_version
molpro_script_gz=molpro-teach-$molpro_version.$(uname|tr '[:upper:]' '[:lower:]')_$(uname -m|sed -e 's/arm64/aarch64/').sh.gz
echo molpro_script_gz=$molpro_script_gz
if [ ! -r $molpro_script_gz ]; then
  wget ${MOLPRO_TEACH_URL}/$molpro_script_gz || echo WARNING molpro-teach not available
fi
if [ -r $molpro_script_gz ]; then
  gunzip -k -f $molpro_script_gz
  molpro_script=$(basename $molpro_script_gz .gz)
  sh $molpro_script -batch -prefix $builddir/molpro
  ls -lR $builddir/molpro/bin
  rm $molpro_script
  sed -i -e 's@MOLPRO_PREFIX=.*$@me=$(realpath $0 2>/dev/null) || me=$0; MOLPRO_PREFIX=$(dirname $(dirname $me))@' $builddir/molpro/bin/molpro
else
  mkdir -p $builddir/molpro
fi


PATH=/usr/bin:$PATH pyi-makespec \
  --add-data JSmol.min.js:. \
  --add-data j2s:./j2s \
  --add-data Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. \
  --add-data README.md:. \
  --add-data doc:./doc \
  --add-data "${versionfile}":. \
  --add-data $builddir/molpro:./molpro \
  --add-data $CONDA_PREFIX/lib/python$(python --version|sed -e 's/.* //' -e 's/\.[0-9]*$//')/site-packages/pymolpro/molpro_input.json:./pymolpro \
  $pyinstaller_opt \
  iMolpro.py || exit 1
sed -i -e '$d' iMolpro.spec
sed -i -e "s/hiddenimports=\[\]/hiddenimports=['scipy._cyutility', 'scipy.sparse._csparsetools', 'scipy._lib.messagestream']/" iMolpro.spec
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

  if [ ! -z "$pkgbuild" ]; then
    pip install macos_pkg_builder
    python <<EOF
from macos_pkg_builder import Packages
def contents(file):
    with open(file,'r') as f:
       return f.read()

pkg_obj = Packages(
    pkg_output="dist/iMolpro-${descriptor}.pkg",
    pkg_bundle_id="net.molpro.iMolpro",
    # pkg_preinstall_script="Samples/MyApp/MyPreinstall.sh",
    # pkg_postinstall_script="Samples/MyApp/MyPostinstall.sh",
    pkg_file_structure={
        "${builddir}/dist/iMolpro.app": "/Applications/iMolpro.app",
    },
    pkg_as_distribution=True,
    pkg_welcome=contents('Package-README.md'),
#    pkg_readme=contents('Package-README.md'),
    pkg_license=contents('Package-License.md'),
    pkg_title="iMolpro",
    # pkg_background="Molpro_Logo_Molpro_Quantum_Chemistry_Software.png",
    pkg_signing_identity="Developer ID Installer: Peter Knowles (LMLY9RHMA3)",
)

assert pkg_obj.build() is True
EOF
  fi

  if [ ! -z "$dmg" ]; then
#  create-dmg --app-drop-link 25 35 --volname iMolpro-"${descriptor}"  --volicon 'Molpro_Logo_Molpro_Quantum_Chemistry_Software.png' dist/iMolpro-"${descriptor}".dmg "${builddir}"/dist
  hdiutil create ./iMolpro.dmg -ov -fs HFS+ -srcfolder "${builddir}"/dist
  echo after first hdiutil
  hdiutil convert ./iMolpro.dmg -format UDZO -o dist/iMolpro-"${descriptor}".dmg
  cp Molpro_Logo_Molpro_Quantum_Chemistry_Software.png "${builddir}"
  (cd "${builddir}" && sips -i Molpro_Logo_Molpro_Quantum_Chemistry_Software.png && DeRez -only icns Molpro_Logo_Molpro_Quantum_Chemistry_Software.png > tmp.rsrc)
  Rez -append "${builddir}"/tmp.rsrc -o dist/iMolpro-"${descriptor}".dmg
  SetFile -a C dist/iMolpro-"${descriptor}".dmg
  rm ./iMolpro.dmg
  fi
else
  rm -rf dist build
  mv "${builddir}"/dist .
  mkdir -p ./dist/iMolpro/_internal/pymolpro
  cp -p $CONDA_PREFIX/lib/python$(python --version|sed -e 's/.* //' -e 's/\.[0-9]*$//')/site-packages/pymolpro/molpro_input.json ./dist/iMolpro/_internal/pymolpro
  for l in libcrypto.so.3 libssl.so.3 ; do
    cp -p $(find ${CONDA_PREFIX} -name $l) $(find dist/iMolpro/_internal -name $l) # because, somehow, pyinstaller picks up the system libcrypto
  done
  if [ ! -z "$tar" ]; then
  tar cjf dist/iMolpro-"${descriptor}".tar.bz2 -C dist iMolpro
  fi
  if [ ! -z "$sh" ]; then
    prefix='/usr'
#    echo '#!/bin/sh' > ${builddir}/preinstall
#    echo "more <<'EOF'" >> ${builddir}/preinstall
#    cat ./Package-README.md ./Package-license.md | sed -e 's/^##* *//' -e 's/\[//g' -e 's/\] *(/, /g' -e 's/))/@@/g' -e 's/)//g' -e 's/@@/)/g' -e 's/\*//g' >> ${builddir}/preinstall
#    echo "EOF" >> ${builddir}/preinstall
#    echo "echo 'Accept license[yN]?'" >> ${builddir}/preinstall
#    echo "exec 0</dev/tty" >> ${builddir}/preinstall
#    echo "read response" >> ${builddir}/preinstall
#    echo 'if [ x"$response" != xy -a x"$response" != xY ]; then kill $$ ; fi' >> ${builddir}/preinstall
    echo '#!/bin/sh' > ${builddir}/postinstall
#    echo 'env' >> ${builddir}/postinstall
    echo "ln -sf ${prefix}/libexec/iMolpro/iMolpro ${prefix}/bin/iMolpro" >> ${builddir}/postinstall
    echo '#!/bin/sh' > ${builddir}/postremove
    echo "rm -rf ${prefix}/libexec/iMolpro ${prefix}/bin/iMolpro" >> ${builddir}/postremove
    echo version=$version
    if [[ $version =~ ^[0-9]*\.[0-9]*\.[0-9]*$ ]] ; then true ; else version="0.0.0" ; fi
    echo version=$version
    for type in deb rpm ; do
      rm -f dist/iMolpro-"${descriptor}".${type}
      dash='-'; if [ $type = rpm ]; then dash='_'; fi
      fpm -s dir -C dist -t ${type} -p dist/imolpro-"${descriptor}".${type} -v "${version}" -n imolpro --prefix=${prefix}/libexec --after-install ${builddir}/postinstall --after-remove ${builddir}/postremove iMolpro
    done
  fi
fi
