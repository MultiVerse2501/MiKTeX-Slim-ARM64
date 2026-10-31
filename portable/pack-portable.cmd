@echo off
setlocal EnableExtensions
rem Build the portable zip from the ARM64 sandbox binaries.
rem The zip version is the MiKTeX version this tree was compiled with.
rem Linker leftovers (.pdb .ilk .lib .exp) stay out. Every PE must be ARM64.
rem The Qt console and its DLL closure are refused.

set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
for %%I in ("%HERE%\..") do set "REPO=%%~fI"

call "%REPO%\miktex-env.cmd"
if errorlevel 1 exit /b 1

set "SRC=%REPO%\build\sandbox\miktex\bin\arm64"
set "STAGE=%HERE%\dist\miktex-portable-arm64"
set "BIN=%STAGE%\texmfs\install\miktex\bin\arm64"
set "BIBER_DIST=%REPO%\recipes\biber\dist\biber.exe"
set "GS_DIST=%REPO%\recipes\ghostscript\dist"
set "ICU_DIR=%REPO%\upstream\vcpkg\installed\arm64-windows\bin"
set "VER_H=%REPO%\build\include\miktex\Version.h"

if not exist "%SRC%\initexmf.exe" (
  echo Sandbox binaries were not found at "%SRC%".
  exit /b 1
)
if not exist "%VER_H%" (
  echo MiKTeX version header was not found at "%VER_H%".
  exit /b 1
)
if not defined VCToolsRedistDir (
  echo VCToolsRedistDir is not set. miktex-env.cmd did not initialize the ARM64 toolset.
  exit /b 1
)

call :pin miktex-tag PIN_MIKTEX
if errorlevel 1 exit /b 1
call :pin biber PIN_BIBER
if errorlevel 1 exit /b 1
call :pin ghostscript PIN_GS
if errorlevel 1 exit /b 1
call :pin icu PIN_ICU
if errorlevel 1 exit /b 1

set "MIKTEX_VER="
for /f "tokens=3" %%V in ('findstr /C:"#define MIKTEX_VERSION_STR " "%VER_H%"') do (
  if not defined MIKTEX_VER set "MIKTEX_VER=%%~V"
)
if not defined MIKTEX_VER (
  echo MIKTEX_VERSION_STR was not found in "%VER_H%".
  exit /b 1
)
if not "%MIKTEX_VER%"=="%PIN_MIKTEX%" (
  echo Built MiKTeX %MIKTEX_VER% does not match versions.txt miktex-tag %PIN_MIKTEX%.
  exit /b 1
)

call :jsonver "%REPO%\recipes\biber\sources.lock.json" ".biber.version" LOCK_BIBER
if errorlevel 1 exit /b 1
call :jsonver "%REPO%\recipes\ghostscript\sources.lock.json" ".ghostscript.version" LOCK_GS
if errorlevel 1 exit /b 1
if not "%LOCK_BIBER%"=="%PIN_BIBER%" (
  echo Biber lock %LOCK_BIBER% does not match versions.txt biber %PIN_BIBER%.
  exit /b 1
)
if not "%LOCK_GS%"=="%PIN_GS%" (
  echo Ghostscript lock %LOCK_GS% does not match versions.txt ghostscript %PIN_GS%.
  exit /b 1
)

for /f "tokens=1 delims=." %%M in ("%PIN_ICU%") do set "ICU_MAJOR=%%M"
if not defined ICU_MAJOR (
  echo versions.txt icu value "%PIN_ICU%" has no major version.
  exit /b 1
)
set "ICU_DT=icudt%ICU_MAJOR%.dll"
set "ICU_IN=icuin%ICU_MAJOR%.dll"
set "ICU_IO=icuio%ICU_MAJOR%.dll"
set "ICU_TU=icutu%ICU_MAJOR%.dll"
set "ICU_UC=icuuc%ICU_MAJOR%.dll"

set "ZIP=%HERE%\dist\miktex-portable-arm64-%MIKTEX_VER%.zip"
echo Staging MiKTeX %MIKTEX_VER% into "%STAGE%"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
if exist "%ZIP%" del /f /q "%ZIP%"
mkdir "%BIN%"
if errorlevel 1 exit /b 1

rem Executables and DLLs only. The sandbox directory also holds .pdb .ilk .lib .exp,
rem plus build-host tools and unit tests that use the same output directory.
robocopy "%SRC%" "%BIN%" *.exe *.dll /NFL /NDL /NJH /NJS /NC /NS
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo robocopy failed with exit %RC%.
  exit /b 1
)

for %%F in (miktex-console.exe miktex-console_admin.exe dxcompiler.dll dxil.dll) do (
  if exist "%BIN%\%%F" (
    echo Slim pack refuses %%F.
    rmdir /s /q "%STAGE%"
    exit /b 1
  )
)
dir /b "%BIN%\Qt6*.dll" >nul 2>&1
if not errorlevel 1 (
  echo Slim pack refuses Qt6 DLLs.
  rmdir /s /q "%STAGE%"
  exit /b 1
)
dir /b "%BIN%\*ui-Qt.dll" >nul 2>&1
if not errorlevel 1 (
  echo Slim pack refuses the Qt UI DLL.
  rmdir /s /q "%STAGE%"
  exit /b 1
)

rem The setup programs are produced by the default CMake options. This zip does not ship them.
rem The other names are build-host tools and unit tests, not TeX programs.
for %%F in (
  miktexsetup.exe
  miktexsetup_standalone.exe
  archive_creator_test1.exe
  archive_extractor_test1.exe
  bintoc.exe
  buildvm.exe
  c4p.exe
  cfg.exe
  fcarch.exe
  gen_test_char.exe
  gen-bases.exe
  gen-fac.exe
  gen-fib.exe
  gen-jacobitab.exe
  gen-psqr.exe
  gen-trialdivtab.exe
  gmp-test.exe
  headerguard.exe
  himktables.exe
  initctangle.exe
  inipool.exe
  inittangle.exe
  j2000.exe
  listpackages.exe
  makebitcounts.exe
  miktexinfo.exe
  minilua.exe
  web-n.exe
) do (
  if exist "%BIN%\%%F" (
    del /f /q "%BIN%\%%F"
    echo Omitted %%F.
  )
)
for %%F in ("%BIN%\core_*test*.exe" "%BIN%\archive_*test*.exe" "%BIN%\gmp-t-*.exe") do (
  if exist "%%~fF" (
    del /f /q "%%~fF"
    echo Omitted %%~nxF.
  )
)

for %%D in (%ICU_DT% %ICU_IN% %ICU_IO% %ICU_TU% %ICU_UC%) do (
  if not exist "%BIN%\%%D" (
    if not exist "%ICU_DIR%\%%D" (
      echo Missing %%D in the sandbox bin and in "%ICU_DIR%".
      exit /b 1
    )
    copy /y "%ICU_DIR%\%%D" "%BIN%\%%D" >nul
    if errorlevel 1 exit /b 1
    echo Copied %%D from the vcpkg ARM64 ICU bin.
  )
)

if not exist "%BIN%\biber.exe" (
  echo biber.exe is not in the sandbox bin.
  exit /b 1
)
if not exist "%BIBER_DIST%" (
  echo Recipe output was not found at "%BIBER_DIST%".
  exit /b 1
)
if not exist "%GS_DIST%\mgs.exe" (
  echo Recipe output was not found at "%GS_DIST%\mgs.exe".
  exit /b 1
)
if not exist "%GS_DIST%\gsdll64.dll" (
  echo gsdll64.dll is not in the Ghostscript recipe output.
  exit /b 1
)
if not exist "%BIN%\mgs.exe" (
  echo mgs.exe is not in the sandbox bin.
  exit /b 1
)
if not exist "%BIN%\gsdll64.dll" (
  echo gsdll64.dll is not in the sandbox bin.
  exit /b 1
)

call :samehash "%BIN%\biber.exe" "%BIBER_DIST%"
if errorlevel 1 (
  echo Biber in the sandbox does not match the recipe output.
  call :showhash
  exit /b 1
)
echo Biber SHA256 matches the recipe output.

for %%F in ("%GS_DIST%\*.exe" "%GS_DIST%\*.dll") do (
  if not exist "%BIN%\%%~nxF" (
    echo %%~nxF from the Ghostscript recipe is not in the sandbox bin.
    exit /b 1
  )
  call :samehash "%BIN%\%%~nxF" "%%~fF"
  if errorlevel 1 (
    echo %%~nxF in the sandbox does not match the Ghostscript recipe.
    call :showhash
    exit /b 1
  )
)
echo Ghostscript recipe files match the sandbox.

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%HERE%\ensure-native-runtime.ps1" -Bin "%BIN%" -RedistRoot "%VCToolsRedistDir%arm64"
if errorlevel 1 exit /b 1

set "PATH_SAVE=%PATH%"
set "PATH=%BIN%;%SystemRoot%\system32;%SystemRoot%"
"%BIN%\initexmf.exe" --version > "%TEMP%\miktex-slim-version.txt" 2>&1
set "VER_RC=%ERRORLEVEL%"
set "PATH=%PATH_SAVE%"
if not "%VER_RC%"=="0" (
  echo initexmf --version failed.
  type "%TEMP%\miktex-slim-version.txt"
  del /f /q "%TEMP%\miktex-slim-version.txt" 2>nul
  exit /b 1
)
findstr /C:"%MIKTEX_VER%" "%TEMP%\miktex-slim-version.txt" >nul
if errorlevel 1 (
  echo initexmf --version did not report %MIKTEX_VER%.
  type "%TEMP%\miktex-slim-version.txt"
  del /f /q "%TEMP%\miktex-slim-version.txt" 2>nul
  exit /b 1
)
del /f /q "%TEMP%\miktex-slim-version.txt" 2>nul
echo initexmf reports MiKTeX %MIKTEX_VER%.

call :expectversion "%BIN%\biber.exe" --version "%LOCK_BIBER%" miktex-slim-biber-version.txt
if errorlevel 1 (
  echo biber --version did not report %LOCK_BIBER%.
  exit /b 1
)
echo Biber reports %LOCK_BIBER%.

call :expectversion "%BIN%\mgs.exe" --version "%LOCK_GS%" miktex-slim-mgs-version.txt
if errorlevel 1 (
  echo mgs --version did not report %LOCK_GS%.
  exit /b 1
)
echo Ghostscript reports %LOCK_GS%.

copy /y "%HERE%\bootstrap-portable.cmd" "%STAGE%\bootstrap-portable.cmd" >nul
if errorlevel 1 exit /b 1
copy /y "%HERE%\miktex-portable.cmd" "%STAGE%\miktex-portable.cmd" >nul
if errorlevel 1 exit /b 1
copy /y "%REPO%\NOTICE.md" "%STAGE%\NOTICE.md" >nul
if errorlevel 1 exit /b 1
>"%STAGE%\version.txt" echo %MIKTEX_VER%

rem Store names as "texmfs/..." . Archiving "." stores "./...", which Explorer
rem rejects: the window is empty and Extract All reports the archive invalid.
echo Writing "%ZIP%"
tar.exe -a -cf "%ZIP%" -C "%STAGE%" bootstrap-portable.cmd miktex-portable.cmd version.txt NOTICE.md texmfs
if errorlevel 1 (
  echo tar failed.
  exit /b 1
)
echo Packed "%ZIP%"
rmdir /s /q "%STAGE%"
if exist "%STAGE%" (
  echo The staging directory is still present: "%STAGE%"
  exit /b 1
)
if exist "%HERE%\dist\miktex-portable-arm64.zip" (
  del /f /q "%HERE%\dist\miktex-portable-arm64.zip"
  if exist "%HERE%\dist\miktex-portable-arm64.zip" (
    echo Could not remove the previous unversioned zip. The current zip is "%ZIP%".
  ) else (
    echo Removed the unversioned zip name.
  )
)
echo Staging directory removed. The distributable is "%ZIP%".
exit /b 0

:pin
set "%~2="
for /f "usebackq tokens=1,* delims==" %%A in ("%REPO%\versions.txt") do (
  if "%%A"=="%~1" set "%~2=%%B"
)
if not defined %~2 (
  echo versions.txt has no %~1 value.
  exit /b 1
)
exit /b 0

:jsonver
set "%~3="
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "$v = (Get-Content -LiteralPath '%~1' -Raw | ConvertFrom-Json)%~2; Set-Content -LiteralPath $env:TEMP\miktex-slim-jsonver.txt -Value $v -Encoding ascii"
if errorlevel 1 (
  echo Could not read %~2 from "%~1".
  exit /b 1
)
set /p %~3=<"%TEMP%\miktex-slim-jsonver.txt"
del /f /q "%TEMP%\miktex-slim-jsonver.txt" 2>nul
if not defined %~3 (
  echo Could not read %~2 from "%~1".
  exit /b 1
)
exit /b 0

:hash
set "HASH_OUT="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%~1" SHA256') do (
  set "HASH_OUT=%%H"
  goto hash_done
)
:hash_done
set "HASH_OUT=%HASH_OUT: =%"
if not defined HASH_OUT exit /b 1
exit /b 0

:samehash
call :hash "%~1"
if errorlevel 1 exit /b 1
set "HASH_LEFT=%HASH_OUT%"
call :hash "%~2"
if errorlevel 1 exit /b 1
if /i not "%HASH_LEFT%"=="%HASH_OUT%" exit /b 1
exit /b 0

:showhash
echo   sandbox %HASH_LEFT%
echo   recipe  %HASH_OUT%
exit /b 0

:expectversion
"%~1" %~2 > "%TEMP%\%~4" 2>&1
findstr /C:"%~3" "%TEMP%\%~4" >nul
if errorlevel 1 (
  type "%TEMP%\%~4"
  del /f /q "%TEMP%\%~4" 2>nul
  exit /b 1
)
del /f /q "%TEMP%\%~4" 2>nul
exit /b 0
