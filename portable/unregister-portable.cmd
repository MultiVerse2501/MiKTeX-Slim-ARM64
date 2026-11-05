@echo off
setlocal EnableExtensions
rem Remove the user Path entry that register-portable.cmd made. After this,
rem deleting the extracted folder is the complete uninstall.
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0user-path.ps1" remove %*
set "RC=%ERRORLEVEL%"
call :hold
exit /b %RC%

:hold
setlocal EnableDelayedExpansion
set "CMDLINE=!cmdcmdline!"
echo(!CMDLINE!| findstr /i /c:" /c " >nul
if not errorlevel 1 pause
endlocal
exit /b 0
