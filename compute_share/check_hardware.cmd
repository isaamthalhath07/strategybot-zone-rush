@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  py -3 doctor.py --torch --output hardware.json
) else (
  "%~1" doctor.py --torch --output hardware.json
)
if errorlevel 1 (
  echo Hardware check failed. Use a Python 3.10 or newer interpreter.
  exit /b 1
)
echo Share hardware.json with the campaign owner. No software was installed.
endlocal
