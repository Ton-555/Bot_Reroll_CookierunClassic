@echo off
setlocal

cd /d "%~dp0"

echo Creating virtual environment in .venv ...
py -3 -m venv .venv
if errorlevel 1 (
    echo Failed to create virtual environment. Make sure Python 3 is installed.
    exit /b 1
)

echo Installing Python libraries ...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Done. Run the app with:
echo   .venv\Scripts\python.exe Gui.py
echo.
pause
