@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ===============================================================
  echo GSI FIRST RUN - installing Python runtime
  echo ===============================================================
  call "OPS\INSTALL_RUNTIME.cmd"
  if errorlevel 1 exit /b %ERRORLEVEL%
)
call "OPS\GSI_DWH_CONTROL.cmd"
