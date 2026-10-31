@echo off
rem Install the MSYS2 CLANGARM64 toolchain Ghostscript 10.08.0 links against.
rem Libraries stay in MSYS2. The staged mgs.exe copies the DLL closure later.
rem Set MSYS2_ROOT when MSYS2 is not on the system drive.

if not defined MSYS2_ROOT set "MSYS2_ROOT=%SystemDrive%\msys64"
set "PACMAN=%MSYS2_ROOT%\usr\bin\pacman.exe"

echo === syncing package databases ===
"%PACMAN%" -Sy --noconfirm || goto :err

echo === installing compiler, shell tools, and Ghostscript libraries ===
"%PACMAN%" -S --needed --noconfirm ^
  autoconf ^
  libtool ^
  make ^
  patch ^
  mingw-w64-clang-aarch64-clang ^
  mingw-w64-clang-aarch64-make ^
  mingw-w64-clang-aarch64-pkgconf ^
  mingw-w64-clang-aarch64-expat ^
  mingw-w64-clang-aarch64-fontconfig ^
  mingw-w64-clang-aarch64-freetype ^
  mingw-w64-clang-aarch64-jbig2dec ^
  mingw-w64-clang-aarch64-libiconv ^
  mingw-w64-clang-aarch64-libidn ^
  mingw-w64-clang-aarch64-libjpeg-turbo ^
  mingw-w64-clang-aarch64-libpaper ^
  mingw-w64-clang-aarch64-libpng ^
  mingw-w64-clang-aarch64-libtiff ^
  mingw-w64-clang-aarch64-openjpeg2 ^
  mingw-w64-clang-aarch64-zlib || goto :err

echo === done ===
goto :eof

:err
echo PREREQS FAILED with errorlevel %errorlevel%
exit /b 1
