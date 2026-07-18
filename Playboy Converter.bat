@echo off
rem Double-click launcher for the Playboy: Cover to Cover converter.
rem Runs the graphical interface using 32-bit Python 3.10.

cd /d "%~dp0"

rem Make sure the Python launcher is available.
where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python does not appear to be installed.
    echo Please install 32-bit Python 3.10 - see README.md for step-by-step
    echo instructions and a download link.
    echo.
    pause
    exit /b 1
)

py -3.10-32 playboy_convert_gui.py
if errorlevel 1 (
    echo.
    echo The converter could not start.
    echo Make sure you installed the 32-bit ^(not 64-bit^) version of
    echo Python 3.10, and that you checked "Add Python to PATH" during setup.
    echo See README.md for the full setup steps.
    echo.
    pause
)
