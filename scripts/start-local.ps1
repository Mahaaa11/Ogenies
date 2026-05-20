Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Starting L&C Emailing (Docker Compose)…"
docker compose up -d --build

Write-Host ""
Write-Host "Open:"
Write-Host "  Web:       http://localhost:3001"
Write-Host "  API:       http://localhost:8000/health"
Write-Host "  phpMyAdmin http://localhost:8080"

