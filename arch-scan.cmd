@echo off
setlocal enabledelayedexpansion
call "%~dp0miktex-env.cmd" >nul
if errorlevel 1 (
  echo arch-scan: miktex-env.cmd failed.
  exit /b 1
)
cd /d "%~dp0build\sandbox\miktex\bin\arm64"
if errorlevel 1 (
  echo arch-scan: sandbox bin was not found.
  exit /b 1
)
set /a total=0
set /a bad=0
for %%F in (*.exe *.dll) do (
  if exist "%%F" (
    set /a total+=1
    dumpbin /headers "%%F" | findstr /C:"machine (ARM64)" >nul
    if errorlevel 1 (
      set /a bad+=1
      echo NON-ARM64: %%F
    )
  )
)
if !total! EQU 0 (
  echo arch-scan: no executables or DLLs in the sandbox bin.
  exit /b 1
)
echo SCANNED=!total! NON_ARM64=!bad!
if !bad! GEQ 1 exit /b 1
exit /b 0
