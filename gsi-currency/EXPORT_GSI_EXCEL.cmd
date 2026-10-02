@echo off
setlocal
cd /d "%~dp0"
if not defined GSI_DATA_ROOT set "GSI_DATA_ROOT=D:\GSI_DATA"
if not defined GSI_DWH_PATH set "GSI_DWH_PATH=%GSI_DATA_ROOT%\warehouse.sqlite"
if not exist ".venv\Scripts\python.exe" (echo ERROR: .venv\Scripts\python.exe not found & pause & exit /b 1)
echo === GSI SNAPSHOT EXCEL EXPORT - NO ETL ===
.venv\Scripts\python.exe -u -m gsi export-excel %*
set "RC=%ERRORLEVEL%"
echo Exit code: %RC%
pause
exit /b %RC%
