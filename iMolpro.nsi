# define name of installer
OutFile "iMolpro.exe"

# define installation directory
InstallDir "$PROGRAMFILES64\iMolpro"

# For removing Start Menu shortcut in Windows 7
# RequestExecutionLevel user

# start default section
Section

    # set the installation directory as the destination for the following actions
    SetOutPath $INSTDIR

    # create the uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    # create a shortcut named "new shortcut" in the start menu programs directory
    # point the new shortcut at the program uninstaller
    CreateShortcut "$SMPROGRAMS\Uninstall iMolpro.lnk" "$INSTDIR\uninstall.exe"
    CreateShortcut "$SMPROGRAMS\iMolpro.lnk" "$INSTDIR\iMolpro.lnk"

    File dist\iMolpro\iMolpro.lnk
    File dist\iMolpro\iMolpro.exe
    File /r dist\iMolpro\_internal
SectionEnd

# uninstaller section start
Section "uninstall"

    # Remove the link from the start menu
    Delete "$SMPROGRAMS\Uninstall iMolpro.lnk"

    # Delete the uninstaller
    Delete $INSTDIR\uninstaller.exe

    RMDir $INSTDIR
# uninstaller section end
SectionEnd