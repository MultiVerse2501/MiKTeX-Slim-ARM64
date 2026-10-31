@echo off
rem Stage 0: install the native ARM64 toolchain, Perl, and Biber's module stack
rem from the MSYS2 clangarm64 repo. One-time. ~340 MB download.
rem Run from a normal cmd prompt; this calls MSYS2 pacman directly.
rem Set MSYS2_ROOT if MSYS2 is not on the system drive.

if not defined MSYS2_ROOT set "MSYS2_ROOT=%SystemDrive%\msys64"
set "PACMAN=%MSYS2_ROOT%\usr\bin\pacman.exe"

echo === syncing package databases ===
"%PACMAN%" -Sy --noconfirm || goto :err

echo === installing toolchain (clang, make, perl) ===
"%PACMAN%" -S --needed --noconfirm ^
  mingw-w64-clang-aarch64-clang ^
  mingw-w64-clang-aarch64-make ^
  mingw-w64-clang-aarch64-perl || goto :err

echo === installing Biber and its native ARM64 module stack ===
rem This pulls Text::BibTeX (btparse), XML::LibXML, Unicode::LineBreak,
rem DateTime, Business::IS[BS]N, etc., all prebuilt for ARM64.
"%PACMAN%" -S --needed --noconfirm ^
  mingw-w64-clang-aarch64-biber || goto :err

echo === done. clangarm64 perl: ===
"%MSYS2_ROOT%\clangarm64\bin\perl.exe" -e "print qq{$^V $^O $Config::Config{archname}\n}"
goto :eof

:err
echo PREREQS FAILED with errorlevel %errorlevel%
exit /b 1
