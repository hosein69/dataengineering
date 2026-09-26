@echo off
setlocal
cd /d "%~dp0"
if not defined GSI_DATA_ROOT set "GSI_DATA_ROOT=D:\GSI_DATA"
if not defined GSI_DWH_PATH set "GSI_DWH_PATH=%GSI_DATA_ROOT%\warehouse.sqlite"
if not exist "%GSI_DATA_ROOT%" mkdir "%GSI_DATA_ROOT%"
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements first. See START_HERE_V28_FA.md
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run app\studio.py --server.address=127.0.0.1
endlocal
