@echo off
setlocal
call "%~dp0GSI_ENV.cmd"
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (echo ERROR: .venv not found & pause & exit /b 1)
.venv\Scripts\python.exe "%~dp0gsi_dwh_ops.py" status
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
