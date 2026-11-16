param([switch]$Offline, [switch]$Tunnel)
$root = Split-Path -Parent $PSScriptRoot
$env:DEMO_SEED = "2035"
$env:DEMO_CLOCK = "live"
$env:DEMO_OFFLINE = $(if ($Offline) { "1" } else { "0" })
if (-not (Test-Path "$root\data\uzex.duckdb")) { python "$root\scripts\build_db.py" }
$api = Start-Process -PassThru -WorkingDirectory "$root\backend" python -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"
Push-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
$web = Start-Process -PassThru npm -ArgumentList "run","dev","--","--host","0.0.0.0","--port","5173"
Pop-Location
if ($Tunnel) { Start-Process cloudflared -ArgumentList "tunnel","--url","http://localhost:5173" }
Write-Host "API  http://localhost:8000/docs"
Write-Host "WEB  http://localhost:5173   (телефон в той же сети: http://<IP ноутбука>:5173)"
Write-Host "Сброс демо: POST http://localhost:8000/demo/reset"
try { Wait-Process -Id $api.Id } finally { Stop-Process -Id $api.Id, $web.Id -ErrorAction SilentlyContinue }
