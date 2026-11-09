@echo off
setlocal
cd /d "%~dp0"
echo Preparing a separate Zone Rush GPU environment in this folder.
py -3.12 -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python is required'"
if errorlevel 1 goto python_missing
py -3.12 -m venv .venv-worker
if errorlevel 1 goto failed
".venv-worker\Scripts\python.exe" -m pip install numpy==2.5.4 --index-url https://pypi.org/simple
if errorlevel 1 goto failed
".venv-worker\Scripts\python.exe" -m pip install -r requirements-gpu.txt
if errorlevel 1 goto failed
".venv-worker\Scripts\python.exe" verify_cuda.py
if errorlevel 1 goto failed
echo Environment checked. Game worker integration is still pending.
pause
exit /b 0
:python_missing
echo Install 64-bit Python 3.12 with the Python launcher, then run this again.
pause
exit /b 1
:failed
echo Setup or GPU verification failed. Keep this window and hardware.json for review.
echo Your global Python environment and NVIDIA driver were not changed.
pause
exit /b 1
