@echo off
setlocal
rem Build dist\mgs.exe. See build.py for stage names.
cd /d "%~dp0" || exit /b 1
python "%~dp0build.py" %*
exit /b %ERRORLEVEL%
