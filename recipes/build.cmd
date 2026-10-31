@echo off
setlocal
rem MiKTeX Slim recipes: build.cmd biber | build.cmd ghostscript
cd /d "%~dp0" || exit /b 1
python "%~dp0build.py" %*
exit /b %ERRORLEVEL%
