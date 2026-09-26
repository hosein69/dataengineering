@echo off
setlocal EnableExtensions
call "%~dp0GSI_ENV.cmd"
cd /d "%~dp0.."
:menu
cls
echo ===============================================================
echo GSI 29.13.0 - DWH / ORCHESTRATION CONTROL
echo DWH: %GSI_DWH_PATH%
echo ===============================================================
echo [1] Status - read only
echo [2] Verify published DWH - integrity/FK/gate/snapshot
echo [3] Refresh data - explicit ETL + gates + atomic publish
echo [4] Start GSI - snapshot only, NO ETL
echo [5] Export Excel - published snapshot only, NO ETL
echo [6] Backup DWH - SQLite online backup API
echo [7] Doctor - code/config/source/regulatory diagnostics
echo [8] Offline diagnostic package
echo [0] Exit
echo.
choice /c 123456780 /n /m "Select: "
set "C=%ERRORLEVEL%"
if "%C%"=="9" goto :eof
if "%C%"=="1" goto status
if "%C%"=="2" goto verify
if "%C%"=="3" goto refresh
if "%C%"=="4" goto startgsi
if "%C%"=="5" goto export
if "%C%"=="6" goto backup
if "%C%"=="7" goto doctor
if "%C%"=="8" goto diag
goto menu

:needpy
if exist ".venv\Scripts\python.exe" exit /b 0
echo ERROR: .venv\Scripts\python.exe not found.
echo Install Python 3.11+ and run: py -3 -m venv .venv
 echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
pause
exit /b 1

:status
call :needpy || goto menu
.venv\Scripts\python.exe "%~dp0gsi_dwh_ops.py" status
pause
goto menu

:verify
call :needpy || goto menu
.venv\Scripts\python.exe "%~dp0gsi_dwh_ops.py" verify
pause
goto menu

:refresh
call :needpy || goto menu
echo === EXPLICIT GSI REFRESH ===
echo DWH: %GSI_DWH_PATH%
.venv\Scripts\python.exe -u -m gsi refresh
set "RC=%ERRORLEVEL%"
echo Refresh exit code: %RC%
if "%RC%"=="0" .venv\Scripts\python.exe "%~dp0gsi_dwh_ops.py" verify
pause
goto menu

:startgsi
call :needpy || goto menu
.venv\Scripts\python.exe -m streamlit run app\studio.py --server.address=127.0.0.1
goto menu

:export
call :needpy || goto menu
.venv\Scripts\python.exe -u -m gsi export-excel
pause
goto menu

:backup
call :needpy || goto menu
.venv\Scripts\python.exe "%~dp0gsi_dwh_ops.py" backup
pause
goto menu

:doctor
call :needpy || goto menu
.venv\Scripts\python.exe -m gsi doctor
pause
goto menu

:diag
if exist "RUN_OFFLINE_DIAGNOSTIC.cmd" (
  call "RUN_OFFLINE_DIAGNOSTIC.cmd"
) else (
  echo ERROR: RUN_OFFLINE_DIAGNOSTIC.cmd not found in product root.
  pause
)
goto menu
