# run_tests.ps1 — Menu-driven test runner for Predictive Maintenance Demo

# ANSI color codes for Windows 10+ with VT support
$ANSI = @{
    Reset = "0"
    Bold = "1"
    Red = "31"
    Green = "32"
    Yellow = "33"
    Blue = "34"
    Cyan = "36"
    Magenta = "35"
}

function Write-Color {
    param(
        [string]$Text,
        [string]$Color
    )
    $code = $ANSI[$Color]
    $prefix = $([char]27) + "[" + $code + "m"
    $suffix = $([char]27) + "[0m"
    Write-Host -NoNewline -ForegroundColor "Default" "$prefix$Text$suffix"
}

function Write-Header {
    Write-Color "========================================" Cyan
    Write-Color "  Predictive Maintenance Demo" Cyan
    Write-Color "========================================" Cyan
    Write-Host ""
}

function Write-Option {
    param(
        [int]$Number,
        [string]$Label,
        [string]$Color
    )
    Write-Color "  $Number" $Color
    Write-Host "  $Label"
}

function Check-Docker {
    try {
        $dockerVersion = docker --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Color "❌ Docker is not installed" Red
            Write-Host "   Visit: https://www.docker.com/products/docker-desktop/"
            exit 1
        }
        
        $dockerPs = docker ps 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Color "❌ Docker is not running" Red
            Write-Host "   Please start Docker Desktop first."
            exit 1
        }
    }
    catch {
        Write-Color "❌ Docker error: $_" Red
        exit 1
    }
}

function Check-Services {
    $services = docker ps | Select-String "api"
    if (-not $services) {
        Write-Color "⚠️  Services are not running" Yellow
        Write-Host "   Starting services..."
        docker compose up -d
        Start-Sleep -Seconds 2
    }
}

function Show-Menu {
    Write-Host ""
    Write-Header
    Write-Color "  1" Green
    Write-Host "  Smoke Test — Verify API is running"
    Write-Color "  2" Green
    Write-Host "  Full Retraining Loop — Trigger drift detection"
    Write-Host ""
    Write-Color "  Choose an option (1-2): " Cyan
    $userInput = Read-Host
    Write-Host ""
    return $userInput
}

function Run-Smoke-Test {
    Write-Color "→ Running smoke test..." Green
    Write-Color "   Testing API connectivity and basic functionality..." Yellow
    Write-Host ""
    docker compose run --rm simulator --mode normal --n-readings 500 --pause
    Write-Host ""
    Write-Color "✓ Smoke test complete!" Green
}

function Run-Retraining-Loop {
    Write-Color "→ Running full retraining loop..." Green
    Write-Color "   This will take 1-5 minutes. Don't close this window." Yellow
    Write-Host ""
    docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo; .\open_results.ps1
    Write-Host ""
    Write-Color "✓ Retraining loop complete!" Green
}

function Main-Menu {
    while ($true) {
        $choice = Show-Menu
        
        if ($choice -eq "1") {
            Check-Docker
            Run-Smoke-Test
        }
        elseif ($choice -eq "2") {
            Check-Docker
            Check-Services
            Run-Retraining-Loop
        }
        else {
            Write-Color "❌ Invalid option. Please run .\run_tests.ps1 and choose 1 or 2." Red
            Write-Host ""
        }
    }
}

# Check if we're running interactively
if (-not $Host.UI.RawUI.KeyAvailable) {
    Write-Color "⚠️  This script requires an interactive terminal." Yellow
    Write-Host "   Please run it from PowerShell (not piped or redirected)."
    exit 1
}

# Run the main menu
Main-Menu