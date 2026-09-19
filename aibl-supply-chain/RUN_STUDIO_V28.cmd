@echo off
cd /d "%~dp0"
if not defined GSI_DWH_PATH set "GSI_DWH_PATH=%LOCALAPPDATA%\GSI\warehouse.sqlite"
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements first. See START_HERE_V28_FA.md
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run app\studio.py
