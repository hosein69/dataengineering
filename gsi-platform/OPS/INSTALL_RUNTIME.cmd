@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
echo === GSI Python runtime bootstrap ===
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo ERROR: Python launcher not found. Install Python 3.11 or newer first.
  pause
  exit /b 1
)
%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)"
if errorlevel 1 (
  echo ERROR: GSI requires Python 3.11 or newer.
  pause
  exit /b 2
)
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if errorlevel 1 exit /b %ERRORLEVEL%
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b %ERRORLEVEL%
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo Runtime installation completed.
.venv\Scripts\python.exe -c "import sys,sqlite3,pandas,numpy,openpyxl,yaml,streamlit,plotly,matplotlib; print('Python',sys.version); print('SQLite',sqlite3.sqlite_version); print('RUNTIME_IMPORTS=PASS')"
pause
