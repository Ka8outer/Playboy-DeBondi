@echo off
rem Run this ONCE after installing Python. It downloads the two small
rem Python add-ons the converter needs (Pillow for images, fpdf2 for PDFs).

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python does not appear to be installed.
    echo Please install 32-bit Python 3.10 first - see README.md.
    echo.
    pause
    exit /b 1
)

echo Installing the required Python packages ^(Pillow and fpdf2^)...
echo.
py -3.10-32 -m pip install -r requirements.txt

echo.
if errorlevel 1 (
    echo Something went wrong installing the packages.
    echo Make sure you installed the 32-bit version of Python 3.10.
) else (
    echo Done. You can now double-click "Playboy Converter.bat" to start.
)
echo.
pause
