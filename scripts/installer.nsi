!include "MUI2.nsh"

;--------------------------------
; Product metadata
!define PRODUCT_NAME    "MoneyMirror"
!define PRODUCT_VERSION "1.0.0"
!define INSTALLER_NAME  "${PRODUCT_NAME}-Setup-${PRODUCT_VERSION}.exe"

;--------------------------------
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\\${INSTALLER_NAME}"
InstallDir "$PROGRAMFILES\\${PRODUCT_NAME}"
InstallDirRegKey HKLM "Software\\${PRODUCT_NAME}" "Install_Dir"

;--------------------------------
; Pages
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
Section "Install"
  ; where to put files
  SetOutPath "$INSTDIR"

  ; copy entire dist\moneymirror directory
  File /r "dist\\moneymirror\\*.*"

  ; record install location in registry
  WriteRegStr HKLM "Software\\${PRODUCT_NAME}" "Install_Dir" "$INSTDIR"

  ; write uninstaller
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

;--------------------------------
Section "Uninstall"
  ; remove registry key
  DeleteRegKey HKLM "Software\\${PRODUCT_NAME}"

  ; remove installed files and directories
  RMDir /r "$INSTDIR"

  ; remove uninstaller
  Delete "$INSTDIR\\Uninstall.exe"
SectionEnd