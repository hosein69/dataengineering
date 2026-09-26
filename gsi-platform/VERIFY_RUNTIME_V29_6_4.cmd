@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found
  pause
  exit /b 1
)
echo === GSI Runtime Verification ===
.venv\Scripts\python.exe -c "import os,gsi,gsi.factsheet,gsi.studio_core.html_export as h; print('CWD=',os.getcwd()); print('GSI_VERSION=',gsi.factsheet.VERSION); print('GSI_MODULE=',gsi.__file__); print('HTML_EXPORT=',h.__file__)"
echo.
echo Expected GSI_VERSION = 29.6.4
pause
