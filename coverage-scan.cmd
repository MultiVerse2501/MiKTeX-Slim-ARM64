@echo off
setlocal
rem Check the ARM64 sandbox against the official Windows package database.
rem Every bin/x64 file the official packages ship has to be built, provided
rem by a recipe, supplied by the pack step, or on the documented exclusion
rem list. See coverage-scan.py.
python "%~dp0coverage-scan.py" %*
exit /b %ERRORLEVEL%
