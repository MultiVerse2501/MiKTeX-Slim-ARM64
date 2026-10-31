@echo off
setlocal EnableExtensions
rem First-run setup for the ARM64 portable tree. Safe to run again.
rem Packages come from the official repository. No x64 binary package is installed.

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

rem Drop inherited MiKTeX paths so this tree cannot attach to another install.
set "ENVLIST=%TEMP%\miktex-env-%RANDOM%.txt"
set MIKTEX_ > "%ENVLIST%" 2>nul
for /f "usebackq delims==" %%K in ("%ENVLIST%") do set "%%K="
del /f /q "%ENVLIST%" 2>nul
set "PATH=%BIN%;%SystemRoot%\system32;%SystemRoot%"

echo [%date% %time%] Creating the portable startup file.
"%BIN%\initexmf.exe" --portable="%INSTALL%"
if errorlevel 1 goto fail
if not exist "%STARTUP%" (
  echo initexmf --portable did not write "%STARTUP%".
  goto fail
)

rem Environment wins over a StartupFile registry value from another install.
set "MIKTEX_COMMONSTARTUPFILE=%STARTUP%"
set "MIKTEX_USERSTARTUPFILE=%STARTUP%"

echo [%date% %time%] Refreshing the file name database.
"%BIN%\miktex.exe" fndb refresh
if errorlevel 1 goto fail

echo [%date% %time%] Updating the package database.
"%BIN%\miktex.exe" packages update-package-database
if errorlevel 1 goto fail

rem One batch, so the fontmaps hook runs after formats.ini, updmap.cfg,
rem the three base map files, and fonts.conf.in are all on disk.
rem An earlier hook failure still leaves the files in place.
rem knuth-lib supplies hyphen.tex. languages configure skips a language
rem whose loader is missing, and LuaTeX aborts without language.dat.lua.
echo [%date% %time%] Installing miktex-config-2.9, miktex-misc, tetex, miktex-fontconfig, and knuth-lib.
"%BIN%\miktex.exe" packages install miktex-config-2.9 miktex-misc tetex miktex-fontconfig knuth-lib
if errorlevel 1 (
  if not exist "%INSTALL%\miktex\config\formats.ini" goto fail
  if not exist "%INSTALL%\miktex\config\updmap.cfg" goto fail
  if not exist "%INSTALL%\miktex\config\languages.ini" goto fail
  if not exist "%INSTALL%\fonts\map\dvips\tetex\dvips35.map" goto fail
  if not exist "%INSTALL%\fonts\map\dvips\tetex\pdftex35.map" goto fail
  if not exist "%INSTALL%\fonts\map\dvips\tetex\ps2pk35.map" goto fail
  if not exist "%INSTALL%\fontconfig\config\fonts.conf.in" goto fail
  if not exist "%INSTALL%\tex\generic\knuth-lib\hyphen.tex" goto fail
  echo [%date% %time%] Package payload is present. Configuring font maps.
  "%BIN%\miktex.exe" fndb refresh
  if errorlevel 1 goto fail
  "%BIN%\miktex.exe" fontmaps configure
  if errorlevel 1 goto fail
)

echo [%date% %time%] Configuring language.dat, language.def, and language.dat.lua.
"%BIN%\miktex.exe" fndb refresh
if errorlevel 1 goto fail
"%BIN%\miktex.exe" languages configure
if errorlevel 1 goto fail
findstr /c:"=USenglish" "%ROOT%\texmfs\config\tex\generic\config\language.dat" >nul
if errorlevel 1 (
  echo language.dat does not list USenglish. hyphen.tex was not visible.
  goto fail
)

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Set-Content -LiteralPath $env:TEMP\miktex-now.txt -Value ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -Encoding ascii"
if errorlevel 1 goto fail
set "NOW="
set /p NOW=<"%TEMP%\miktex-now.txt"
del /f /q "%TEMP%\miktex-now.txt" 2>nul
if not defined NOW (
  echo Could not read the current Unix time.
  goto fail
)
echo [%date% %time%] Enabling package install on first use.
"%BIN%\initexmf.exe" --set-config-value "[MPM]AutoInstall=1"
if errorlevel 1 goto fail
"%BIN%\initexmf.exe" --set-config-value "[MPM]LastUserUpdateCheck=%NOW%"
if errorlevel 1 goto fail

if exist "%ROOT%\texmfs\config\miktex\config\issues.json" del /f /q "%ROOT%\texmfs\config\miktex\config\issues.json"
if exist "%INSTALL%\miktex\config\issues.json" del /f /q "%INSTALL%\miktex\config\issues.json"

echo [%date% %time%] Building pdftex, pdflatex, xetex, xelatex, luatex, and lualatex.
"%BIN%\initexmf.exe" --enable-installer --dump=pdftex --dump=pdflatex --dump=xetex --dump=xelatex --dump=luatex --dump=lualatex
if errorlevel 1 goto fail

if exist "%ROOT%\texmfs\config\miktex\config\issues.json" del /f /q "%ROOT%\texmfs\config\miktex\config\issues.json"
if exist "%INSTALL%\miktex\config\issues.json" del /f /q "%INSTALL%\miktex\config\issues.json"

>"%DONE%" echo bootstrap completed %date% %time%
echo [%date% %time%] Bootstrap complete.
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
