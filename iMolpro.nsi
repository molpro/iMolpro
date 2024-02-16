OutFile "iMolpro.exe"

InstallDir "$PROGRAMFILES64\iMolpro"

Section
    SetOutPath $INSTDIR

    WriteUninstaller "$INSTDIR\uninstall.exe"

    CreateShortcut "$SMPROGRAMS\Uninstall iMolpro.lnk" "$INSTDIR\uninstall.exe"
    CreateShortcut "$SMPROGRAMS\iMolpro.lnk" "$INSTDIR\iMolpro.exe"

    File dist\iMolpro\iMolpro.exe
    File /r dist\iMolpro\_internal
SectionEnd

Section "uninstall"
    Delete "$SMPROGRAMS\Uninstall iMolpro.lnk"
    Delete "$SMPROGRAMS\iMolpro.lnk"
    Delete $INSTDIR\uninstall.exe
    Delete $INSTDIR\iMolpro.exe
    RMDir /r $INSTDIR\_internal
    RMDir $INSTDIR
SectionEnd