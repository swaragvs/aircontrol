@echo off
setlocal
title AirControl Windows Builder
cd /d "%~dp0"

echo Installing Windows packaging dependencies...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo Creating application icon...
python make_icon.py
if errorlevel 1 goto :fail

echo Building AirControl tray application...
python -m PyInstaller --noconfirm --clean --noconsole --onedir --name AirControl --icon icon.ico --distpath build\windows-dist --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 tray.py
if errorlevel 1 goto :fail

echo.
echo Build complete: "%~dp0build\windows-dist\AirControl\AirControl.exe"
echo Compile AirControl.iss with Inno Setup to create the installer.
pause
exit /b 0

:fail
echo.
echo Build failed. Review the error output above.
pause
exit /b 1
