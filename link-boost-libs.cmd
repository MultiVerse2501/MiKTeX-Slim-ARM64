@echo off
setlocal EnableExtensions
rem MiKTeX looks up the libboost_ prefix. vcpkg ships boost_*.lib.
rem Hardlink libboost_*.lib beside each boost_*.lib in the static-md install.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "LIBDIR=%ROOT%\upstream\vcpkg\installed\arm64-windows-static-md\lib"
if not exist "%LIBDIR%" (
  echo Boost lib directory not found: "%LIBDIR%"
  exit /b 1
)
pushd "%LIBDIR%"
dir /b boost_*.lib >nul 2>&1
if errorlevel 1 (
  echo No boost_*.lib files in "%LIBDIR%".
  popd
  exit /b 1
)
for %%F in (boost_*.lib) do (
  if not exist "lib%%F" (
    fsutil hardlink create "lib%%F" "%%F"
    if errorlevel 1 (
      popd
      exit /b 1
    )
    echo linked lib%%F
  )
)
popd
echo Boost libboost_ hardlinks are in place.
exit /b 0
