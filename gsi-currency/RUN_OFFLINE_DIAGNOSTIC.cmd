@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title GSI Offline Diagnostic

echo ============================================================
echo GSI OFFLINE DIAGNOSTIC - VISIBLE RUNNER
echo ============================================================
echo Package folder: %CD%
echo Data folder:    %CD%
echo.

echo [CHECK] Looking for Python 3...
set "PYEXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYEXE="%~dp0.venv\Scripts\python.exe""
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 set "PYEXE=py -3"
)
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
  echo [FATAL] Python 3 was not found in PATH.
  echo Install/use the same Python environment that runs GSI, then retry.
  echo.
  pause
  exit /b 9009
)

echo [OK] Python command: %PYEXE%
%PYEXE% --version
if errorlevel 1 (
  echo [FATAL] Python exists but could not start.
  echo.
  pause
  exit /b 9009
)

echo.
echo [START] Diagnostic begins now.
echo Long stages show a RUNNING heartbeat every 10 seconds.
echo Detailed logs are written under offline_feedback.
echo.
set PYTHONDONTWRITEBYTECODE=1
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
set PYTHONUNBUFFERED=1

%PYEXE% -u -B offline_validation\run_offline_diagnostic.py --data-dir "%CD%" %*
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
  echo Diagnostic finished. Gate PASS.
) else if "%RC%"=="2" (
  echo Diagnostic finished. Gate HOLD - this is a valid diagnostic result.
) else (
  echo Diagnostic stopped with runner error. Exit code: %RC%
)
echo Feedback is under: %CD%\offline_feedback
echo Send the newest GSI_FEEDBACK_*.zip file back to ChatGPT.
echo ============================================================
echo.
pause
exit /b %RC%
