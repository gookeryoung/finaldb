; finaldb.nsi - NSIS 安装包脚本
; 编译命令：makensis finaldb.nsi（在 installer/ 目录执行；相对路径按脚本所在目录解析）

!define APP_NAME "finaldb"
!define APP_VERSION "0.1.0"
!define APP_PUBLISHER "gooker_young"
!define APP_REGKEY "Software\${APP_NAME}"
!define APP_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

Unicode true
ManifestDPIAware true

Name "${APP_NAME}"
OutFile "..\dist\${APP_NAME}-${APP_VERSION}-setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey HKCU "${APP_REGKEY}" "InstallDir"
RequestExecutionLevel user

; 现代化界面
!include "MUI2.nsh"
!include "FileFunc.nsh"

!define MUI_ABORTWARNING

; 页面
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 语言
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Section "MainSection"
    SetOutPath "$INSTDIR"

    ; 主程序文件（PyInstaller 单文件产物，位于仓库根 dist/ 目录）
    File "..\dist\finaldb.exe"

    ; 快捷方式
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_NAME}.exe" "" \
        "$INSTDIR\${APP_NAME}.exe" 0
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_NAME}.exe"

    ; 注册表
    WriteRegStr HKCU "${APP_REGKEY}" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "${APP_REGKEY}" "Version" "${APP_VERSION}"
    WriteRegStr HKCU "${APP_UNINST_KEY}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "${APP_UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "${APP_UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "${APP_UNINST_KEY}" "DisplayIcon" "$INSTDIR\${APP_NAME}.exe"
    WriteRegStr HKCU "${APP_UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegDWORD HKCU "${APP_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${APP_UNINST_KEY}" "NoRepair" 1

    ; 卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    ; 删除文件（保留用户工作区数据目录，卸载不误删数据）
    Delete "$INSTDIR\finaldb.exe"
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; 清理注册表
    DeleteRegKey HKCU "${APP_UNINST_KEY}"
    DeleteRegKey HKCU "${APP_REGKEY}"
SectionEnd
