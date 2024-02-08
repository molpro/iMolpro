cmd.exe /c conda install -c conda-forge -y --file=requirements.txt


$versionfile = ( $env:TMP, "\VERSION" ) -join ""
$PWD = (Get-Item .).FullName
git config --global --add safe.directory "$PWD"
$version = $(git describe --tags --dirty --always)
echo "$version" > "$versionfile"

pyinstaller --noconfirm `
  --add-data=JSmol.min.js:. `
    --add-data=j2s:./j2s `
      --add-data=Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. `
        --add-data=README.md:. `
          --add-data=doc:.\doc `
            --add-data="$versionfile":. `
              $pyinstaller_opt iMolpro.py

# $descriptor = ($version, '.', $(uname), '.', $(uname -m)
