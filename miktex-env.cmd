@echo off
rem Project root is the directory that contains this script.
rem Qt is not part of this build. A QT_ROOT inherited from the environment is cleared.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VSINSTALL="
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64 -property installationPath`) do set "VSINSTALL=%%I"
if not defined VSINSTALL (
  echo miktex-env: no Visual Studio install with the ARM64 C++ toolset.
  exit /b 1
)
call "%VSINSTALL%\VC\Auxiliary\Build\vcvarsall.bat" arm64
if errorlevel 1 exit /b 1

set "QT_ROOT="
rem Static Boost (dynamic CRT) plus dynamic ICU. vcvarsall already put MSVC first.
set "VCPKG_ROOT=%ROOT%\upstream\vcpkg"
set "BOOST_ROOT=%VCPKG_ROOT%\installed\arm64-windows-static-md"
set "CMAKE_PREFIX_PATH=%BOOST_ROOT%;%VCPKG_ROOT%\installed\arm64-windows"
set "PATH=%PATH%;%VCPKG_ROOT%\installed\arm64-windows\bin"
rem MSYS2 stays after MSVC so it cannot replace link.exe, cmake or python.
rem clangarm64 is last and only supplies xsltproc plus its DLLs.
if not defined MSYS2_ROOT set "MSYS2_ROOT=%SystemDrive%\msys64"
set "PATH=%PATH%;%MSYS2_ROOT%\usr\bin"
set "PATH=%PATH%;%MSYS2_ROOT%\clangarm64\bin"
title MiKTeX Slim ARM64 build
