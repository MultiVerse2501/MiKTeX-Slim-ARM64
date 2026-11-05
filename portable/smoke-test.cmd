@echo off
setlocal
rem Exercise the packed portable zip the way a user would: extract, bootstrap,
rem compile, run Biber and Ghostscript. See smoke-test.py.
python "%~dp0smoke-test.py" %*
exit /b %ERRORLEVEL%
