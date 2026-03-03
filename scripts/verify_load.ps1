param(
    [string]$HostUrl = "http://127.0.0.1:5000",
    [int]$Users = 120,
    [int]$SpawnRate = 20,
    [string]$RunTime = "1m",
    [double]$MaxP95Ms = 1000,
    [double]$MaxFailureRatio = 0.01,
    [int]$MinTotalRequests = 500
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
Set-Location $workspace

$python = Join-Path $workspace "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Python venv not found: $python"
}

$resultsPrefix = Join-Path $workspace "loadtests\results\weave"
$statsCsv = "${resultsPrefix}_stats.csv"

if (Test-Path $statsCsv) {
    Remove-Item $statsCsv -Force
}

$serverProc = Start-Process -FilePath $python -ArgumentList "-m", "waitress", "--host=127.0.0.1", "--port=5000", "app:app" -PassThru

try {
    Start-Sleep -Seconds 2

    & $python -m locust -f "loadtests/locustfile.py" --headless --host $HostUrl --users $Users --spawn-rate $SpawnRate --run-time $RunTime --stop-timeout 10 --csv $resultsPrefix
    if ($LASTEXITCODE -ne 0) {
        throw "Locust execution failed with exit code $LASTEXITCODE"
    }

    & $python "loadtests/assert_locust.py" --stats $statsCsv --max-p95-ms $MaxP95Ms --max-failure-ratio $MaxFailureRatio --min-total-requests $MinTotalRequests
    if ($LASTEXITCODE -ne 0) {
        throw "Threshold assertion failed"
    }

    Write-Host "Load verification passed."
}
finally {
    if ($serverProc -and -not $serverProc.HasExited) {
        Stop-Process -Id $serverProc.Id -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
}
