param(
  [Parameter(Mandatory=$true)][string]$PostgresDsn,
  [string]$SqlitePath = '.\weave.db'
)

$pythonExe = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
if (!(Test-Path $pythonExe)) { $pythonExe = 'python' }

Write-Host '[1/3] SQLite 백업 생성' -ForegroundColor Cyan
& $pythonExe 'scripts/backup_db.py' --db-path $SqlitePath --backup-dir '.\backups'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/3] PostgreSQL 이관' -ForegroundColor Cyan
& $pythonExe 'scripts/migrate_sqlite_to_postgres.py' --sqlite $SqlitePath --postgres-dsn $PostgresDsn
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[3/3] 핵심 테이블 건수 비교' -ForegroundColor Cyan
& $pythonExe 'scripts/compare_sqlite_postgres_counts.py' --sqlite $SqlitePath --postgres-dsn $PostgresDsn
exit $LASTEXITCODE
