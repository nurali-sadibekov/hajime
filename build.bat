@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem ===========================================================================
rem  Builds release\Hajime-Setup.exe, a Windows installer for Hajime.
rem
rem  Usage:  build.bat          full build (lint + tests, app, installer)
rem          build.bat fast     skip lint and tests
rem
rem  Needs:  Python 3.10+ with Tkinter (the "py" launcher), internet access once.
rem          Inno Setup 6 is installed automatically with winget if it is missing.
rem
rem  Settings come from the environment or from a build.env file next to this script:
rem      HAJIME_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
rem      HAJIME_SUPABASE_ANON_KEY=sb_publishable_...      (the PUBLISHABLE key, never secret)
rem  Optional code signing (strongly recommended before distributing):
rem      SIGN_PFX=C:\path\to\certificate.pfx
rem      SIGN_PASSWORD=...
rem ===========================================================================

set "FAST="
if /i "%~1"=="fast" set "FAST=1"
set "CONFIG_WRITTEN="

if exist "build.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("build.env") do set "%%A=%%B"
)

echo.
echo [1/7] Checking Python
py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 10)" 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.10+ with Tkinter is required. Install it from https://www.python.org
    goto :fail
)

echo [2/7] Checking Supabase settings
if "%HAJIME_SUPABASE_URL%"=="" goto :nosettings
if "%HAJIME_SUPABASE_ANON_KEY%"=="" goto :nosettings
goto :settingsok
:nosettings
echo ERROR: HAJIME_SUPABASE_URL and HAJIME_SUPABASE_ANON_KEY are not set.
echo        Put them in build.env next to this script, or set them in the environment.
goto :fail
:settingsok

echo [3/7] Preparing build environment (.build-venv)
if not exist ".build-venv\Scripts\python.exe" (
    py -3 -m venv .build-venv || goto :fail
)
set "PY=%~dp0.build-venv\Scripts\python.exe"
"%PY%" -m pip install --quiet --disable-pip-version-check --upgrade pip || goto :fail
"%PY%" -m pip install --quiet --disable-pip-version-check ".[exe,dev]" || goto :fail

if defined FAST goto :skiptests
echo [4/7] Running lint and tests
"%PY%" -m ruff check . || goto :fail
"%PY%" -m pytest -q || goto :fail
goto :package
:skiptests
echo [4/7] Skipped lint and tests (fast mode)

:package
set "VERSION="
for /f %%V in ('call "%PY%" packaging\print_version.py') do set "VERSION=%%V"
if not defined VERSION (
    echo ERROR: could not read the version from hajime\__init__.py
    goto :fail
)
echo [5/7] Packaging Hajime %VERSION%
"%PY%" packaging\write_config.py || goto :fail
set "CONFIG_WRITTEN=1"
"%PY%" packaging\make_icon.py >nul || goto :fail
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name Hajime ^
    --icon packaging\hajime.ico ^
    --collect-data customtkinter ^
    --add-data "hajime\assets;hajime\assets" ^
    --hidden-import websocket ^
    --hidden-import hajime._bundled_config ^
    --paths . packaging\launcher.py || goto :fail
if not exist "dist\Hajime\Hajime.exe" (
    echo ERROR: PyInstaller did not produce dist\Hajime\Hajime.exe
    goto :fail
)

echo [6/7] Looking for Inno Setup
call :findiscc
if not defined ISCC (
    echo Inno Setup 6 was not found. Installing it with winget...
    winget install --id JRSoftware.InnoSetup -e --scope user --silent ^
        --accept-package-agreements --accept-source-agreements
    call :findiscc
)
if not defined ISCC (
    echo ERROR: Inno Setup 6 is required. Install it from https://jrsoftware.org/isdl.php
    echo        and run build.bat again.
    goto :fail
)

call :sign "dist\Hajime\Hajime.exe"
if errorlevel 1 goto :fail

echo [7/7] Building the installer
"%ISCC%" /Qp /DAppVersion=%VERSION% installer\hajime.iss || goto :fail
call :sign "release\Hajime-Setup.exe"
if errorlevel 1 goto :fail

if exist "hajime\_bundled_config.py" del /q "hajime\_bundled_config.py"
echo.
echo ==========================================================================
echo  Done: release\Hajime-Setup.exe  (Hajime %VERSION%)
if not defined SIGN_PFX (
    echo  NOTE: not code-signed. Windows SmartScreen will warn users until you sign it.
    echo        Set SIGN_PFX and SIGN_PASSWORD in build.env to sign.
)
echo ==========================================================================
endlocal
exit /b 0

:findiscc
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do set "ISCC=%%I"
)
exit /b 0

:sign
if not defined SIGN_PFX exit /b 0
set "SIGNTOOL="
for /f "delims=" %%S in ('where signtool.exe 2^>nul') do set "SIGNTOOL=%%S"
if not defined SIGNTOOL for /f "delims=" %%S in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\signtool.exe" 2^>nul ^| findstr /i "x64"') do set "SIGNTOOL=%%S"
if not defined SIGNTOOL (
    echo ERROR: SIGN_PFX is set but signtool.exe was not found. Install the Windows SDK.
    exit /b 1
)
"%SIGNTOOL%" sign /f "%SIGN_PFX%" /p "%SIGN_PASSWORD%" /fd sha256 /tr http://timestamp.digicert.com /td sha256 %1
exit /b %errorlevel%

:fail
if defined CONFIG_WRITTEN if exist "hajime\_bundled_config.py" del /q "hajime\_bundled_config.py"
echo.
echo BUILD FAILED.
endlocal
exit /b 1
