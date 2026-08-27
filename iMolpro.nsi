/*
OutFile "iMolpro.exe"

InstallDir "$PROGRAMFILES64\iMolpro"

!define MULTIUSER_INSTALLMODE_DEFAULT_CURRENTUSER
!include MultiUser.nsh

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
*/
/*

This example script installs a simple application for a single user.

If multiple users on the same machine run this installer, each user
will end up with a separate install that is not affected by
update/removal operations performed by other users.

Per-user installers should only write to HKCU and
folders inside the users profile.

*/

!define NAME "iMolpro"
!define REGPATH_UNINSTSUBKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}"
Name "${NAME}"
OutFile "${NAME}.exe"
Unicode True
RequestExecutionLevel User ; We don't need UAC elevation
InstallDir "" ; Don't set a default $InstDir so we can detect /D= and InstallDirRegKey
InstallDirRegKey HKCU "${REGPATH_UNINSTSUBKEY}" "UninstallString"

!include LogicLib.nsh
!include WinCore.nsh
!include Integration.nsh
!include WinMessages.nsh
!include StrFunc.nsh
${StrStr}
${StrRep}


Page Directory
Page InstFiles

Uninstpage UninstConfirm
Uninstpage InstFiles


Function .onInit
  SetShellVarContext Current

  ${If} $InstDir == "" ; No /D= nor InstallDirRegKey?
    GetKnownFolderPath $InstDir ${FOLDERID_UserProgramFiles} ; This folder only exists on Win7+
    StrCmp $InstDir "" 0 +2
    StrCpy $InstDir "$LocalAppData\Programs" ; Fallback directory

    StrCpy $InstDir "$InstDir\$(^Name)"
  ${EndIf}
FunctionEnd

Function un.onInit
  SetShellVarContext Current
FunctionEnd


Section "Program files (Required)"
  SectionIn Ro

  SetOutPath $InstDir
  WriteUninstaller "$InstDir\Uninst.exe"
  WriteRegStr HKCU "${REGPATH_UNINSTSUBKEY}" "DisplayName" "${NAME}"
  WriteRegStr HKCU "${REGPATH_UNINSTSUBKEY}" "DisplayIcon" "$InstDir\iMolpro.exe,0"
  WriteRegStr HKCU "${REGPATH_UNINSTSUBKEY}" "UninstallString" '"$InstDir\Uninst.exe"'
  WriteRegStr HKCU "${REGPATH_UNINSTSUBKEY}" "QuietUninstallString" '"$InstDir\Uninst.exe" /S'
  WriteRegDWORD HKCU "${REGPATH_UNINSTSUBKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${REGPATH_UNINSTSUBKEY}" "NoRepair" 1
    File dist\iMolpro\iMolpro.exe
    File /r dist\iMolpro\_internal

  ;!tempfile APP
  ;!makensis '-v2 "-DOUTFILE=${APP}" "-DNAME=NSISPerUserAppExample" -DCOMPANY=Nullsoft "AppGen.nsi"' = 0
  ;File "/oname=$InstDir\iMolpro.exe" "${APP}" ; Pretend that we have a real application to install
  ;!delfile "${APP}"
SectionEnd

Section "Start Menu shortcut"
  CreateShortcut /NoWorkingDir "$SMPrograms\${NAME}.lnk" "$InstDir\iMolpro.exe"
SectionEnd

; Put iMolpro on PATH so it can be launched from the command line, for
; parity with macOS ("Install command line tool...", see cli_install.py)
; and Linux (already on PATH via pip/deb/rpm packaging). Unlike the macOS
; wrapper, this needs no special-case launch logic: Windows already starts
; a fresh iMolpro process on every launch (Start Menu, file association),
; so there is no existing single-instance behaviour to preserve here --
; a plain PATH entry pointing at iMolpro.exe is a complete equivalent.
; This only takes effect in shells opened after the (un)install; already-open
; ones won't see the change, same as for any other PATH-modifying installer.
Section -AddToPath
  ReadRegStr $0 HKCU "Environment" "Path"
  ${StrStr} $1 "$0;" "$InstDir;"
  ${If} $1 == ""
    ${If} $0 == ""
      WriteRegExpandStr HKCU "Environment" "Path" "$InstDir"
    ${Else}
      WriteRegExpandStr HKCU "Environment" "Path" "$0;$InstDir"
    ${EndIf}
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000
  ${EndIf}
SectionEnd

Section -un.RemoveFromPath
  ReadRegStr $0 HKCU "Environment" "Path"
  ${If} $0 != ""
    ${un.StrRep} $0 "$0" "$InstDir;" ""
    ${un.StrRep} $0 "$0" ";$InstDir" ""
    ${un.StrRep} $0 "$0" "$InstDir" ""
    WriteRegExpandStr HKCU "Environment" "Path" "$0"
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000
  ${EndIf}
SectionEnd

/*
This Section registers a fictional .molpro file extension and the net.molpro.iMolpro ProgId.
Proprietary file types are encouraged (by Microsoft) to use long file extensions and ProgIds that include the company name.

When registering with "Open With" your executable should ideally have a somewhat unique name,
otherwise there could be a naming collision with a different application (with the same name) installed on the same machine.

REGISTER_DEFAULTPROGRAMS is not defined because proprietary file types do not typically use the Default Programs functionality.
If your application registers a standard file type such as .mp3 or .html or a protocol like HTTP it should register as a Default Program.
It should also register as a client (https://docs.microsoft.com/en-us/windows/win32/shell/reg-middleware-apps#common-registration-elements-for-all-client-types).
*/
!define ASSOC_EXT ".molpro"
!define ASSOC_PROGID "net.molpro.iMolpro"
!define ASSOC_VERB "iMolpro"
!define ASSOC_APPEXE "iMolpro.exe"
!define REGISTER_DEFAULTPROGRAMS

; A .molpro project is a directory, so it can never be double-clicked into
; iMolpro the way a bundle can on macOS -- Explorer always browses into a
; folder regardless of any file-type registration. The next best thing is
; to let iMolpro open the individual files inside an already-open project
; folder, matching the extensions __main__.py already handles as file-open
; events on macOS. These are common, widely-owned extensions, so (unlike
; .molpro above) they are only added to "Open With", never made the default.
!macro RegisterOpenWith EXT
  WriteRegNone ShCtx "Software\Classes\${EXT}\OpenWithList" "${ASSOC_APPEXE}"
  WriteRegNone ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\SupportedTypes" "${EXT}"
!macroend

!macro UnregisterOpenWith EXT
  DeleteRegValue ShCtx "Software\Classes\${EXT}\OpenWithList" "${ASSOC_APPEXE}"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${EXT}\OpenWithList"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${EXT}"
!macroend

Section -ShellAssoc
  # Register file type
  WriteRegStr ShCtx "Software\Classes\${ASSOC_PROGID}\DefaultIcon" "" "$InstDir\${ASSOC_APPEXE},0"
  ;WriteRegStr ShCtx "Software\Classes\${ASSOC_PROGID}\shell\${ASSOC_VERB}" "" "net.molpro.iMolpro App" [Optional]
  ;WriteRegStr ShCtx "Software\Classes\${ASSOC_PROGID}\shell\${ASSOC_VERB}" "MUIVerb" "@$InstDir\${ASSOC_APPEXE},-42" ; WinXP+ [Optional] Localizable verb display name
  WriteRegStr ShCtx "Software\Classes\${ASSOC_PROGID}\shell\${ASSOC_VERB}\command" "" '"$InstDir\${ASSOC_APPEXE}" "%1"'
  WriteRegStr ShCtx "Software\Classes\${ASSOC_EXT}" "" "${ASSOC_PROGID}"

  # Register "Open With" [Optional]
  WriteRegNone ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithList" "${ASSOC_APPEXE}" ; Win2000+ [Optional]
  ;WriteRegNone ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithProgids" "${ASSOC_PROGID}" ; WinXP+ [Optional]
  WriteRegStr ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\shell\open\command" "" '"$InstDir\${ASSOC_APPEXE}" "%1"'
  WriteRegStr ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}" "FriendlyAppName" "iMolpro" ; [Optional]
  WriteRegStr ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}" "ApplicationCompany" "Molpro" ; [Optional]
  WriteRegNone ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\SupportedTypes" "${ASSOC_EXT}" ; [Optional] Only allow "Open With" with specific extension(s) on WinXP+

  # Also offer iMolpro as an "Open With" option for the individual files
  # inside a project (input/output/XML), without touching their existing
  # default associations.
  !insertmacro RegisterOpenWith ".xml"
  !insertmacro RegisterOpenWith ".out"
  !insertmacro RegisterOpenWith ".inp"

  # Register "Default Programs" [Optional]
  !ifdef REGISTER_DEFAULTPROGRAMS
  WriteRegStr ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\Capabilities" "ApplicationDescription" "GUI for Molpro quantum chemistry projects"
  WriteRegStr ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\Capabilities\FileAssociations" "${ASSOC_EXT}" "${ASSOC_PROGID}"
  WriteRegStr ShCtx "Software\RegisteredApplications" "iMolpro" "Software\Classes\Applications\${ASSOC_APPEXE}\Capabilities"
  !endif

  ${NotifyShell_AssocChanged}
SectionEnd


Section -un.ShellAssoc
  # Unregister file type
  ClearErrors
  DeleteRegKey ShCtx "Software\Classes\${ASSOC_PROGID}\shell\${ASSOC_VERB}"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${ASSOC_PROGID}\shell"
  ${IfNot} ${Errors}
    DeleteRegKey ShCtx "Software\Classes\${ASSOC_PROGID}\DefaultIcon"
  ${EndIf}
  ReadRegStr $0 ShCtx "Software\Classes\${ASSOC_EXT}" ""
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${ASSOC_PROGID}"
  ${IfNot} ${Errors}
  ${AndIf} $0 == "${ASSOC_PROGID}"
    DeleteRegValue ShCtx "Software\Classes\${ASSOC_EXT}" ""
    DeleteRegKey /IfEmpty ShCtx "Software\Classes\${ASSOC_EXT}"
  ${EndIf}

  # Unregister "Open With"
  DeleteRegKey ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}"
  DeleteRegValue ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithList" "${ASSOC_APPEXE}"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithList"
  DeleteRegValue ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithProgids" "${ASSOC_PROGID}"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\${ASSOC_EXT}\OpenWithProgids"
  DeleteRegKey /IfEmpty  ShCtx "Software\Classes\${ASSOC_EXT}"

  !insertmacro UnregisterOpenWith ".xml"
  !insertmacro UnregisterOpenWith ".out"
  !insertmacro UnregisterOpenWith ".inp"

  # Unregister "Default Programs"
  !ifdef REGISTER_DEFAULTPROGRAMS
  DeleteRegValue ShCtx "Software\RegisteredApplications" "iMolpro"
  DeleteRegKey ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}\Capabilities"
  DeleteRegKey /IfEmpty ShCtx "Software\Classes\Applications\${ASSOC_APPEXE}"
  !endif

  # Attempt to clean up junk left behind by the Windows shell
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Search\JumplistData" "$InstDir\${ASSOC_APPEXE}"
  DeleteRegValue HKCU "Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache" "$InstDir\${ASSOC_APPEXE}.FriendlyAppName"
  DeleteRegValue HKCU "Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache" "$InstDir\${ASSOC_APPEXE}.ApplicationCompany"
  DeleteRegValue HKCU "Software\Microsoft\Windows\ShellNoRoam\MUICache" "$InstDir\${ASSOC_APPEXE}" ; WinXP
  DeleteRegValue HKCU "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store" "$InstDir\${ASSOC_APPEXE}"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" "${ASSOC_PROGID}_${ASSOC_EXT}"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" "Applications\${ASSOC_APPEXE}_${ASSOC_EXT}"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\${ASSOC_EXT}\OpenWithProgids" "${ASSOC_PROGID}"
  DeleteRegKey /IfEmpty HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\${ASSOC_EXT}\OpenWithProgids"
  DeleteRegKey /IfEmpty HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\${ASSOC_EXT}\OpenWithList"
  DeleteRegKey /IfEmpty HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\${ASSOC_EXT}"
  ;DeleteRegKey HKCU "Software\Microsoft\Windows\Roaming\OpenWith\FileExts\${ASSOC_EXT}"
  ;DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs\${ASSOC_EXT}"

  ${NotifyShell_AssocChanged}
SectionEnd

!macro DeleteFileOrAskAbort path
  ClearErrors
  Delete "${path}"
  IfErrors 0 +3
    MessageBox MB_ABORTRETRYIGNORE|MB_ICONSTOP 'Unable to delete "${path}"!' IDRETRY -3 IDIGNORE +2
    Abort "Aborted"
!macroend

Section -Uninstall
    ;Delete $INSTDIR\iMolpro.exe
  !insertmacro DeleteFileOrAskAbort "$InstDir\iMolpro.exe"
    RMDir /r $INSTDIR\_internal
  Delete "$InstDir\Uninst.exe"
  RMDir "$InstDir"
  DeleteRegKey HKCU "${REGPATH_UNINSTSUBKEY}"

  ${UnpinShortcut} "$SMPrograms\${NAME}.lnk"
  Delete "$SMPrograms\${NAME}.lnk"
SectionEnd