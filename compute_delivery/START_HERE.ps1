$ErrorActionPreference = 'Stop'
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONINSPECT -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONSAFEPATH -ErrorAction SilentlyContinue
$zrDelivery = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'delivery.json') -Raw | ConvertFrom-Json
$zrExpectedExeSha = $zrDelivery.approved_runtime.executable_sha256
function Test-ZrRuntime([string] $zrPath) {
    try {
        $zrStream = [System.IO.File]::OpenRead($zrPath)
        $zrHasher = [System.Security.Cryptography.SHA256]::Create()
        try { $zrExeSha = [System.BitConverter]::ToString($zrHasher.ComputeHash($zrStream)).Replace('-','').ToLowerInvariant() }
        finally { $zrStream.Dispose(); $zrHasher.Dispose() }
        if ($zrExeSha -ne $zrExpectedExeSha) { return $false }
        $zrProbe = & $zrPath (Join-Path $PSScriptRoot 'RUN_WORK.py') --runtime-probe 2>$null
        return ($LASTEXITCODE -eq 0 -and ($zrProbe -contains 'APPROVED_RUNTIME_MATCH'))
    } catch { return $false }
}
try {
    Write-Host 'Finding your previously approved Python worker. Nothing is installed.'
    $zrCandidates = @(
        (Join-Path $PSScriptRoot 'compute_share\.venv-worker\Scripts\python.exe'),
        (Join-Path $PSScriptRoot '..\compute_share\.venv-worker\Scripts\python.exe'),
        (Join-Path $PSScriptRoot '..\..\compute_share\.venv-worker\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE 'ZoneRush\compute_share\.venv-worker\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE 'Downloads\compute_share\.venv-worker\Scripts\python.exe')
    )
    $zrSavedSettings = Join-Path $PSScriptRoot 'job_settings.json'
    if (Test-Path -LiteralPath $zrSavedSettings -PathType Leaf) {
        $zrSaved = Get-Content -LiteralPath $zrSavedSettings -Raw | ConvertFrom-Json
        if ($zrSaved.python_executable) { $zrCandidates = @([string]$zrSaved.python_executable) + $zrCandidates }
    }
    foreach ($zrPathPython in (Get-Command python,python.exe -ErrorAction SilentlyContinue)) {
        if ($zrPathPython.Source -and $zrPathPython.Source -notlike '*WindowsApps*') { $zrCandidates += $zrPathPython.Source }
    }
    $zrPython = $null
    foreach ($zrCandidate in $zrCandidates) {
        if ((Test-Path -LiteralPath $zrCandidate -PathType Leaf) -and (Test-ZrRuntime $zrCandidate)) {
            $zrPython = $zrCandidate
            break
        }
    }
    if (-not $zrPython) {
        if ($env:ZONE_RUSH_CHECK_PACKAGE_ONLY -eq '1') { throw 'No exact approved runtime found in the known candidates.' }
        Add-Type -AssemblyName System.Windows.Forms
        $zrDialog = New-Object System.Windows.Forms.OpenFileDialog
        $zrDialog.Title = 'Choose the exact Python environment used in your successful qualification'
        $zrDialog.Filter = 'Python interpreter (python.exe)|python.exe'
        $zrDialog.InitialDirectory = Join-Path $env:USERPROFILE 'Downloads'
        if ($zrDialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No approved Python selected. No work started.' }
        $zrPython = $zrDialog.FileName
        $zrDialog.Dispose()
        if (-not (Test-ZrRuntime $zrPython)) { throw 'This is a different Python build from your approved return. Contact the owner; do not reinstall.' }
    }
    $zrArguments = @((Join-Path $PSScriptRoot 'RUN_WORK.py'))
    if ($env:ZONE_RUSH_CHECK_PACKAGE_ONLY -eq '1') { $zrArguments += '--check-package' }
    & $zrPython @zrArguments
    $zrExit = $LASTEXITCODE
    if ($env:ZONE_RUSH_CHECK_PACKAGE_ONLY -ne '1') { Read-Host 'Press Enter to close this window' }
    exit $zrExit
} catch {
    Write-Host ('Stopped: ' + $_.Exception.Message)
    Write-Host 'Keep this job folder and results. Nothing was installed.'
    if ($env:ZONE_RUSH_CHECK_PACKAGE_ONLY -ne '1') { Read-Host 'Press Enter to close this window' }
    exit 1
}
