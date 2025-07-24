# --- Application Metadata ---
!define APP_NAME "MoneyMirror"
!define APP_EXE  "moneymirror.exe"
!define VERSION "1.0.0"

# --- Source & Output Files ---
# Use the GITHUB_WORKSPACE variable to create an absolute path to the PyInstaller output
!define SRC_DIR  "${GITHUB_WORKSPACE}\dist"
!define OUT_FILE "${GITHUB_WORKSPACE}\dist\MoneyMirror-Setup.exe"

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