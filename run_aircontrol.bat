@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

python "%~dp0aircontrol.py"

echo.
echo AirControl has stopped.
pause
