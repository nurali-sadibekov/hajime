@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import customtkinter" 2>nul || py -3 -m pip install --quiet customtkinter
py -3 -m hajime
if errorlevel 1 (
    echo.
    echo Could not start Hajime. Make sure Python 3.10+ with Tkinter is installed.
    pause
)
