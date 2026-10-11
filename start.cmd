@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 goto use_py
)

where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto no_python
goto use_python

:use_py
py -3 -X utf8 app.py --open %*
goto finished

:use_python
python -X utf8 app.py --open %*
goto finished

:no_python
echo Python 3.10 or newer was not found.
echo Install Python, then reopen this launcher.
pause
exit /b 1

:finished
set "adlab_exit_code=%errorlevel%"
if not "%adlab_exit_code%"=="0" echo The application stopped with exit code %adlab_exit_code%.
pause
exit /b %adlab_exit_code%
