!include "MUI2.nsh"

;--------------------------------
; Product metadata
!define PRODUCT_NAME    "MoneyMirror"
!define PRODUCT_VERSION "2.0.1"
!define INSTALLER_NAME  "${PRODUCT_NAME}-Setup-${PRODUCT_VERSION}.exe"

;--------------------------------
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
; write the installer out into the repo-root/dist folder
OutFile "..\\dist\\${INSTALLER_NAME}"

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
  SetOutPath "$INSTDIR"

  ; copy everything from the PyInstaller output
  File /r "..\\dist\\moneymirror\\*.*"

  ; record install location in registry
  WriteRegStr HKLM "Software\\${PRODUCT_NAME}" "Install_Dir" "$INSTDIR"

  ; write uninstaller into the install folder
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

;--------------------------------
Section "Uninstall"
  DeleteRegKey HKLM "Software\\${PRODUCT_NAME}"
  RMDir /r "$INSTDIR"
  Delete "$INSTDIR\\Uninstall.exe"
SectionEnd
