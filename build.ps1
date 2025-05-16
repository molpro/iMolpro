get-content ENV | foreach {
  $name, $value = $_.split('=')
  set-content env:\$name $value
}

$molpro_root='molpro-teach-' + $env:molpro_version + '.windows_x64'
$molpro_zip=${molpro_root} + 'exe'
$full_url = $env:MOLPRO_TEACH_URL + '/' + $molpro_zip
curl -O $full_url
7z -o${molpro_root} x ${molpro_zip}


cmd.exe /c conda install -c conda-forge -y --file=requirements.txt m2-base nsis python=3.9

$versionfile = ( $env:TMP, "\VERSION") -join ""
$PWD = (Get-Item .).FullName
git config --global --add safe.directory "$PWD"
$version = $( git describe --tags --dirty --always )
echo "$version" > "$versionfile"



If (Test-Path -path dist)
{
    rm dist -r -fo
}
$cp = $env:CONDA_PREFIX
pyinstaller --noconfirm `
  --add-data=JSmol.min.js:. `
    --add-data=j2s:./j2s `
      --add-data=Molpro_Logo_Molpro_Quantum_Chemistry_Software.png:. `
        --add-data=README.md:. `
          --add-data=doc:.\doc `
            --add-data="$versionfile":. `
            --add-data ${molpro_root}:.\molpro `
            --add-data=$cp\Library\usr\bin\nohup.exe:. `
            --add-data=$cp\Library\usr\bin\bash.exe:. `
            --add-data=$cp\Library\usr\bin\mkdir.exe:. `
            --add-data=$cp\Library\usr\bin\dirname.exe:. `
            --add-data=$cp\Library\usr\bin\ps.exe:. `
            --add-data=$cp\rsync:.\rsync `
              $pyinstaller_opt iMolpro.py


$descriptor = ($version, 'Windows', $( uname -m )) -join "."
echo descriptor $descriptor
& $cp\NSIS\makensis.exe iMolpro.nsi
If (Test-Path -path iMolpro-$descriptor.exe)
{
    rm iMolpro-$descriptor.exe
}
Rename-item iMolpro.exe iMolpro-$descriptor.exe