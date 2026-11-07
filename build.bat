@echo off
setlocal
cd /d "%~dp0"
set "TIDY_PY=python"
if defined VIRTUAL_ENV set "TIDY_PY=%VIRTUAL_ENV%\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "TIDY_PY=.venv\Scripts\python.exe"
"%TIDY_PY%" -m PyInstaller --noconfirm --clean TidyDesk.spec
exit /b %ERRORLEVEL%

