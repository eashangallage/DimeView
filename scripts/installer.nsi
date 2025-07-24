!define APP_NAME "MoneyMirror"
!define APP_EXE  "moneymirror.exe"
!define SRC_DIR  "${PROJECT}\dist\moneymirror"
!define OUT_FILE "${PROJECT}\output\MoneyMirror-Setup.exe"

Name "${APP_NAME} Setup"
OutFile "${OUT_FILE}"
InstallDir "$PROGRAMFILES\${APP_NAME}"
RequestExecutionLevel user

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${SRC_DIR}\*.*"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd
