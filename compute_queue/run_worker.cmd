@echo off
setlocal
cd /d "%~dp0\.."
if not exist "compute_share\.venv-worker\Scripts\python.exe" goto missing_environment
if not exist ".cache\compute_queue\worker.json" goto missing_config
"compute_share\.venv-worker\Scripts\python.exe" -m compute_queue.queue work --config ".cache\compute_queue\worker.json" --device cuda
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Worker stopped. Keep this window for review; no unverified work receives credit.
pause
exit /b 1
:missing_environment
echo Use the existing compute_share setup_gpu.cmd first. Reuse this same environment for all jobs.
pause
exit /b 1
:missing_config
echo A private worker configuration is required at .cache\compute_queue\worker.json.
echo The owner must supply it privately after an approved HTTPS connection is tested.
pause
exit /b 1
