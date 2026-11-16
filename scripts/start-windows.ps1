#requires -Version 5.1
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function New-RandomHex([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
}

function New-FernetKey {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $encoded = [Convert]::ToBase64String($bytes)
    return $encoded.Replace("+", "-").Replace("/", "_")
}

Write-Host "ALOSTORA-RADIUS - local test setup" -ForegroundColor Cyan
Write-Host "Project folder: $ProjectRoot"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed. Install Docker Desktop, then run this script again."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is not running. Start Docker Desktop and wait until it says Engine running."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is unavailable. Update Docker Desktop."
}

if (-not (Test-Path ".env")) {
    $dbPassword = New-RandomHex 24
    $envContent = @"
POSTGRES_DB=alostora_radius
POSTGRES_USER=alostora
POSTGRES_PASSWORD=$dbPassword
DATABASE_URL=postgresql+psycopg://alostora:$dbPassword@db:5432/alostora_radius
APP_ENV=development
APP_SECRET_KEY=$(New-RandomHex 48)
JWT_ACCESS_TOKEN_MINUTES=30
CREDENTIAL_ENCRYPTION_KEY=$(New-FernetKey)
ROUTER_SECRET_ENCRYPTION_KEY=$(New-FernetKey)
RADIUS_INTERNAL_API_KEY=$(New-RandomHex 48)
RADIUS_COA_ENABLED=false
RADIUS_COA_PORT=1700
RADIUS_COA_TIMEOUT_SECONDS=2
"@
    Set-Content -Path ".env" -Value $envContent -Encoding ASCII
    Write-Host "Created a private local .env with generated secrets." -ForegroundColor Green
} else {
    Write-Host "Existing .env found; it will be preserved." -ForegroundColor Yellow
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose configuration is invalid. Check the local .env file."
}

Write-Host "Building and starting the local test services..." -ForegroundColor Cyan
docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    throw "The services did not start successfully. Inspect with: docker compose logs"
}

Write-Host "Waiting for the API and database readiness check..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(5)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health/ready" -TimeoutSec 4
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 3
    }
}

docker compose ps
if (-not $ready) {
    Write-Host "The containers started, but API readiness was not confirmed within five minutes." -ForegroundColor Yellow
    Write-Host "Inspect logs with: docker compose logs --tail=150 api db"
    exit 1
}

Write-Host ""
Write-Host "ALOSTORA-RADIUS is running locally." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:5173"
Write-Host "API health: http://localhost:8000/health"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "Create the first administrator in a NEW PowerShell window:" -ForegroundColor Cyan
Write-Host 'docker compose exec api python -m app.scripts.create_admin --username admin --display-name "مدير النظام"'
Write-Host "The command will ask you to set the password securely."
Write-Host ""
Write-Host "Stop without deleting test data: docker compose down"
Write-Host "Delete the local test database permanently: docker compose down -v"
Write-Host "Do not connect a production MikroTik or import real cards during this first test." -ForegroundColor Yellow
