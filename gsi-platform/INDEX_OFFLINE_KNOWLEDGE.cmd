@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -B offline_knowledge\LOAD_INTO_KNOWLEDGE_DESK.py
) else (
  python -B offline_knowledge\LOAD_INTO_KNOWLEDGE_DESK.py
)
endlocal
