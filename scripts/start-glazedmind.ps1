$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

function Write-Step([string]$message) {
    Write-Host "`n>> $message" -ForegroundColor Cyan
}

function Stop-WithMessage([string]$message) {
    Write-Host "`n$message" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "       GlazedMind Team Launcher" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Magenta

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "Docker Desktop is not installed. Install it from https://www.docker.com/products/docker-desktop/ and run this file again."
}

$envPath = Join-Path $projectRoot ".env"
$examplePath = Join-Path $projectRoot ".env.example"

if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Step "First-time secure configuration"
    Write-Host "Your credentials stay only in this computer and are ignored by Git." -ForegroundColor DarkGray
    $ollamaKey = Read-Host "Paste your company Ollama API key"
    $mondayToken = Read-Host "Paste your Monday API token"
    if ([string]::IsNullOrWhiteSpace($ollamaKey) -or [string]::IsNullOrWhiteSpace($mondayToken)) {
        Stop-WithMessage "Both credentials are required. Nothing was saved."
    }
    $content = Get-Content -LiteralPath $examplePath | ForEach-Object {
        if ($_.StartsWith("OLLAMA_API_KEY=")) { "OLLAMA_API_KEY=$ollamaKey" }
        elseif ($_.StartsWith("MONDAY_API_TOKEN=")) { "MONDAY_API_TOKEN=$mondayToken" }
        else { $_ }
    }
    [System.IO.File]::WriteAllLines($envPath, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Configuration saved locally." -ForegroundColor Green
}

Write-Step "Checking Docker Desktop"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        Stop-WithMessage "Docker Desktop is installed but is not running. Open it, wait until it is ready, and try again."
    }
    Write-Host "Starting Docker Desktop. This may take a minute..." -ForegroundColor Yellow
    Start-Process -FilePath $dockerDesktop
    $dockerReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    }
    if (-not $dockerReady) {
        Stop-WithMessage "Docker Desktop did not become ready. Verify Docker and run this file again."
    }
}

Write-Step "Building and starting GlazedMind"
docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Docker could not build GlazedMind. Check your internet connection and Docker Desktop."
}

Write-Step "Waiting for the Help Desk services"
$backendReady = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3
        if ($health.status -eq "ok") {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $backendReady) {
    docker compose logs --tail 30 backend
    Stop-WithMessage "The backend did not become healthy. The latest diagnostic messages are shown above."
}

Write-Step "Checking the Knowledge Base"
try {
    $catalog = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge/documents" -TimeoutSec 10
    $documentCount = @($catalog.documents).Count
} catch {
    $documentCount = 0
}

if ($documentCount -eq 0) {
    Write-Host "Indexing the verified DOCX guides for the first time..." -ForegroundColor Yellow
    docker compose exec -T backend python scripts/build_knowledge_index.py
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "The Knowledge Base could not be indexed. Confirm your Ollama access and try again."
    }
} else {
    Write-Host "$documentCount verified guides are already indexed." -ForegroundColor Green
}

Write-Host "`nGlazedMind is ready." -ForegroundColor Green
Write-Host "Workspace: http://localhost:3000" -ForegroundColor White
Write-Host "API health: http://localhost:8000/health" -ForegroundColor DarkGray
Start-Process "http://localhost:3000"
Start-Sleep -Seconds 2
