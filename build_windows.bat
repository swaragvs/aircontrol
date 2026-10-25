@echo off
setlocal
title AirControl Windows Builder
cd /d "%~dp0"

echo Installing Windows packaging dependencies...
python -m pip install aiohttp pynput qrcode pystray pillow pyinstaller
if errorlevel 1 goto :fail

echo Creating application icon...
python make_icon.py
if errorlevel 1 goto :fail

echo Building AirControl tray application...
python -m PyInstaller --noconfirm --clean --noconsole --onedir --name AirControl --icon icon.ico --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 tray.py
if errorlevel 1 goto :fail

echo.
echo Build complete: "%~dp0dist\AirControl\AirControl.exe"
echo Compile AirControl.iss with Inno Setup to create the installer.
pause
exit /b 0

:fail
echo.
echo Build failed. Review the error output above.
pause
exit /b 1
