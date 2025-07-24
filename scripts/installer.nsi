# --- Application Metadata ---
!define APP_NAME "MoneyMirror"
!define APP_EXE  "moneymirror.exe"
!define VERSION "1.0.0"

# --- Source & Output Files ---
!define SRC_DIR  "dist\moneymirror"
!define OUT_FILE "output\MoneyMirror-Setup.exe"

# --- Installer Settings ---
RequestExecutionLevel admin
InstallDir "$PROGRAMFILES64\${APP_NAME}"
OutFile "${OUT_FILE}"

# --- Modern User Interface ---
!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

# --- Installation Section ---
Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${SRC_DIR}\*.*"

  # --- Create Uninstaller ---
  WriteUninstaller "$INSTDIR\uninstall.exe"

  # --- Create Shortcuts ---
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

# --- Uninstallation Section ---
Section "Uninstall"
  # Remove files and directories
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR"

  # Remove shortcuts
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
SectionEnd