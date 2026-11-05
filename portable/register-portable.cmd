@echo off
setlocal EnableExtensions
rem Add texmfs\install\miktex\bin\arm64 to the user Path, so every tool in
rem this release is callable from any shell. Undo: unregister-portable.cmd.
rem -Front puts the entry first instead of last. See user-path.ps1.
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0user-path.ps1" add %*
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
