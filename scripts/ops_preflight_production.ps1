param(
  [string]$Env = $(if ($env:WEAVE_ENV) { $env:WEAVE_ENV } else { 'production' }),
  [string]$HealthUrl = $(if ($env:WEAVE_HEALTH_URL) { $env:WEAVE_HEALTH_URL } else { 'http://127.0.0.1:5000/healthz' })
)

$pythonExe = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
if (!(Test-Path $pythonExe)) { $pythonExe = 'python' }

& $pythonExe 'scripts/preflight_ops_check.py' --env $Env --health-url $HealthUrl
exit $LASTEXITCODE
