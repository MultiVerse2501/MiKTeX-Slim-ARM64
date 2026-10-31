@echo off
setlocal EnableExtensions
rem Open a command prompt whose PATH is this portable ARM64 MiKTeX.
rem The first launch runs bootstrap-portable.cmd. There is no Qt console.
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
