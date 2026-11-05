@echo off
setlocal EnableExtensions
rem The setup entry: the first launch bootstraps the tree and offers an
rem optional user Path registration; every launch opens a command prompt
rem whose PATH is this portable ARM64 MiKTeX. There is no Qt console.
rem A failure from Explorer pauses so the message stays on screen.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "INSTALL=%ROOT%\texmfs\install"
set "BIN=%INSTALL%\miktex\bin\arm64"
set "STARTUP=%INSTALL%\miktex\config\miktexstartup.ini"
set "DONE=%INSTALL%\miktex\config\bootstrap-complete.txt"

if not exist "%BIN%\initexmf.exe" (
  echo This folder does not contain the ARM64 MiKTeX binaries.
  echo Expected: "%BIN%\initexmf.exe"
  goto fail
)

if not exist "%STARTUP%" goto bootstrap
if not exist "%DONE%" goto bootstrap
goto launch

:bootstrap
call "%~dp0bootstrap-portable.cmd"
if errorlevel 1 (
  echo Bootstrap failed.
  goto fail
)

:offer-register
rem One-time offer during setup. Registration is optional and can also be
rem done later with register-portable.cmd; an unanswered prompt defaults
rem to no.
set "REGISTER="
set /p "REGISTER=Add the tools to your user Path, callable from any shell? [y/N] "
if /i not "%REGISTER%"=="y" (
  echo Skipped. register-portable.cmd does this later; unregister-portable.cmd undoes it.
  goto launch
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0user-path.ps1" add
if errorlevel 1 (
  echo Registration failed. The prompt still opens; register-portable.cmd can retry later.
  call :hold
  goto launch
)
echo Registered. unregister-portable.cmd removes the entry again.
goto launch

:launch
endlocal & set "PATH=%BIN%;%SystemRoot%\system32;%SystemRoot%" & set "MIKTEX_COMMONSTARTUPFILE=%STARTUP%" & set "MIKTEX_USERSTARTUPFILE=%STARTUP%" & start "MiKTeX ARM64" /D "%ROOT%" cmd /k
exit /b 0

:fail
call :hold
exit /b 1

:hold
setlocal EnableDelayedExpansion
set "CMDLINE=!cmdcmdline!"
echo(!CMDLINE!| findstr /i /c:" /c " >nul
if not errorlevel 1 pause
endlocal
exit /b 0
