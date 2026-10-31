@echo off
setlocal EnableExtensions
rem Check out the MiKTeX and vcpkg commits named in versions.txt.
rem Safe to run again. The ARM64 patch is applied only when it is not already there.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "MIKTEX_COMMIT="
set "VCPKG_COMMIT="
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%\versions.txt") do (
  if "%%A"=="miktex" set "MIKTEX_COMMIT=%%B"
  if "%%A"=="vcpkg" set "VCPKG_COMMIT=%%B"
)
if not defined MIKTEX_COMMIT (
  echo versions.txt has no miktex commit.
  exit /b 1
)
if not defined VCPKG_COMMIT (
  echo versions.txt has no vcpkg commit.
  exit /b 1
)

call :checkout miktex https://github.com/MiKTeX/miktex.git "%MIKTEX_COMMIT%"
if errorlevel 1 exit /b 1
call :checkout vcpkg https://github.com/microsoft/vcpkg.git "%VCPKG_COMMIT%"
if errorlevel 1 exit /b 1

set "PATCH=%ROOT%\patches\miktex-arm64.patch"
git -C "%ROOT%\upstream\miktex" apply --reverse --check "%PATCH%"
if not errorlevel 1 (
  echo ARM64 patch already applied.
  exit /b 0
)
git -C "%ROOT%\upstream\miktex" apply --check "%PATCH%"
if errorlevel 1 (
  echo The ARM64 patch does not apply. Remove upstream\miktex and run fetch-upstream.cmd again.
  exit /b 1
)
git -C "%ROOT%\upstream\miktex" apply "%PATCH%"
if errorlevel 1 exit /b 1
echo ARM64 patch applied.
exit /b 0

:checkout
set "NAME=%~1"
set "URL=%~2"
set "COMMIT=%~3"
set "DIR=%ROOT%\upstream\%NAME%"
if not exist "%DIR%\.git" (
  git init "%DIR%"
  if errorlevel 1 exit /b 1
)
git -C "%DIR%" remote get-url origin >nul 2>&1
if errorlevel 1 (
  git -C "%DIR%" remote add origin "%URL%"
  if errorlevel 1 exit /b 1
)
git -C "%DIR%" fetch --depth 1 origin "%COMMIT%"
if errorlevel 1 exit /b 1
git -C "%DIR%" checkout --detach FETCH_HEAD
if errorlevel 1 exit /b 1
echo %NAME% is %COMMIT%.
exit /b 0
