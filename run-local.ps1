param(
    [switch]$PrintOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$envPath = Join-Path $repoRoot ".env"
if (-not (Test-Path $envPath)) {
    $localTemplate = Join-Path $repoRoot ".env.local.example"
    $defaultTemplate = Join-Path $repoRoot ".env.example"
    if (Test-Path $localTemplate) {
        Copy-Item $localTemplate $envPath
        Write-Host "Created .env from .env.local.example. Update it with your local values, then rerun this script."
    }
    elseif (Test-Path $defaultTemplate) {
        Copy-Item $defaultTemplate $envPath
        Write-Host "Created .env from .env.example. Update it with your local values, then rerun this script."
    }
    else {
        throw "No .env template found in the repository root."
    }
    exit 0
}

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
        return
    }

    $name, $value = $line -split "=", 2
    if (-not $name) {
        return
    }

    if ($null -eq $value) {
        $value = ""
    }

    [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
}

$venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    throw "Virtual environment activation script not found at $venvActivate"
}

$command = "uvicorn backend.app.main:app --reload"

Write-Host "Loaded environment from $envPath"
Write-Host "Backend command: $command"
Write-Host "Frontend command: cd frontend; npm run dev"

if ($PrintOnly) {
    exit 0
}

. $venvActivate
Invoke-Expression $command
