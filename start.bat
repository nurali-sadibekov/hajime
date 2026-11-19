@echo off
setlocal
cd /d "%~dp0"
py -3 -m hajime
if errorlevel 1 (
    echo.
    echo Could not start Hajime. Make sure Python 3 and Tkinter are installed.
    pause
)
