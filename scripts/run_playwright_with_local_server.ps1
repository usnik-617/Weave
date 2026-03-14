$ErrorActionPreference = 'Stop'

$spec = if ($args.Length -ge 1 -and $args[0]) { $args[0] } else { "tests/api-error-cases.spec.js" }
$project = if ($args.Length -ge 2 -and $args[1]) { $args[1] } else { "chromium" }
$reporter = if ($args.Length -ge 3 -and $args[2]) { $args[2] } else { "line" }

$env:WEAVE_PORT = "5111"
$env:WEAVE_DB_PATH = "instance/playwright.db"
$env:PLAYWRIGHT_USE_SYSTEM_CHROME = "1"
$env:PLAYWRIGHT_EXTERNAL_SERVER = "1"

$venvPython = Join-Path (Get-Location).Path ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

$workspace = (Get-Location).Path
$stdoutLog = Join-Path $workspace "tmp_playwright_server_stdout.log"
$stderrLog = Join-Path $workspace "tmp_playwright_server_stderr.log"
if (Test-Path $stdoutLog) { Remove-Item $stdoutLog -Force }
if (Test-Path $stderrLog) { Remove-Item $stderrLog -Force }

$server = Start-Process -FilePath $pythonExe -ArgumentList "app.py" -PassThru -WorkingDirectory $workspace -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

try {
  $healthUrl = "http://127.0.0.1:5111/healthz"
  $ready = $false
  for ($i = 0; $i -lt 120; $i++) {
    try {
      $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        $ready = $true
        break
      }
    } catch {}
    Start-Sleep -Seconds 1
  }
  if (-not $ready) {
    $stderrTail = ""
    if (Test-Path $stderrLog) {
      $stderrTail = (Get-Content $stderrLog -Tail 60 -ErrorAction SilentlyContinue) -join "`n"
    }
    throw "로컬 서버 시작 실패: $healthUrl 응답 없음`n$stderrTail"
  }

  & npx.cmd playwright test $spec --project=$project --reporter=$reporter
  exit $LASTEXITCODE
} finally {
  if ($server -and -not $server.HasExited) {
    Stop-Process -Id $server.Id -Force
  }
}
