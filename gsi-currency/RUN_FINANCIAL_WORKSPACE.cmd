@echo off
setlocal
rem GSI financial workspace (cash flow and FX commitment). Reads the published DWH snapshot only.
rem V29.9: uses the package .venv, runs from the package root so .streamlit\config.toml applies,
rem and binds to 127.0.0.1 so financial data is not exposed on the local network.
cd /d "%~dp0"
if not defined GSI_DATA_ROOT set "GSI_DATA_ROOT=D:\GSI_DATA"
if not defined GSI_DWH_PATH set "GSI_DWH_PATH=%GSI_DATA_ROOT%\warehouse.sqlite"
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements first: run 00_RUN_GSI.cmd
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run app\cashflow.py --server.address=127.0.0.1
endlocal
